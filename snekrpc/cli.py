"""Command-line entry points for interacting with local and remote servers."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import stat
import sys
from collections.abc import Callable
from inspect import Parameter as Param
from typing import Any, BinaryIO, cast

import msgspec

from . import codec, errors, formatter, interface, logs, registry, service, transport, utils
from .utils.function import ParameterSpec, SignatureSpec

DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'
DATE_FORMAT = '%Y-%m-%d'
TIME_FORMAT = '%H:%M:%S'

COLLECTION_TYPES = frozenset(['list', 'dict'])
Args = argparse.Namespace
CommandMeta = dict[str, Any]

log = logs.get(__name__)


def main() -> None:
    """Convenient entry-point."""
    Parser().main()


class Parser:
    """Builds CLI parsers for both client and server workflows."""

    def __init__(self) -> None:
        """Initialize the base parser and global argument definitions."""
        # global args
        self.base_parser = argparse.ArgumentParser(add_help=False)
        self.add_global_args(self.base_parser)

    def main(self) -> None:
        """Processes command-line arguments and calls any selected command."""

        # temp parser to grab connection arguments
        parser = argparse.ArgumentParser(add_help=False, parents=[self.base_parser])
        parser.add_argument(
            '-h', '--help', action='store_true', help='show this help message and exit'
        )
        parser.add_argument('rest', nargs=argparse.REMAINDER, help=argparse.SUPPRESS)

        args, extra_args = parser.parse_known_args()

        logs.init(args.verbose)

        # import built-in modules
        registry.init()

        # import additional modules
        for imp in args.imports:
            utils.path.import_module(imp)

        if args.list:
            meta = cast(
                registry.Registry[Any],
                {
                    'codecs': codec.REGISTRY,
                    'formatters': formatter.REGISTRY,
                    'services': service.REGISTRY,
                    'transports': transport.REGISTRY,
                }[args.list],
            )

            # select an output formatter
            fmt = None
            try:
                fmt = formatter.create(args.format)
            except Exception as e:
                if args.verbose:
                    raise
                parser.error(str(e))
            assert fmt is not None

            fmt.process(meta.names())
            return

        # parser for transport and service args
        parser = argparse.ArgumentParser(parents=[self.base_parser])

        transport_cls = transport.get(args.url)
        if isinstance(transport_cls, Exception):
            self.add_transport_exception(parser, args.url.scheme, transport_cls)
        else:
            self.add_transport_args(parser, transport_cls)

        # add service arguments
        used_aliases = set()
        for name in sorted(args.services):
            name, alias = parse_alias(name)
            service_cls = service.get(name)

            alias = alias or name
            if alias in used_aliases:
                raise ValueError(f'duplicate service alias: {alias}')
            used_aliases.add(alias)

            self.add_service_args(parser, service_cls, alias)

        # collect transport and service args
        sub_args = parser.parse_args(extra_args)
        trn_args, svc_args = self.get_prefixed_args(sub_args)

        trn_name = args.url.scheme
        trn = transport.create(args.url, **trn_args.get(trn_name, {}))

        # start client or server
        if args.server_mode:
            # help
            if args.help:
                parser.print_help()
                parser.exit()
            if args.version is True:
                parser.error('expected a version string')
            if args.rest:
                parser.error('unrecognized arguments: {}'.format(' '.join(args.rest)))
            self.start_server(trn, args, svc_args)
        else:
            try:
                self.start_client(trn, parser, args)
            except Exception as e:
                err = '{}\nconnection required for help on remote services'

                if args.help:
                    parser.print_help()
                    print(err.format(e), file=sys.stderr)
                    parser.exit()

                if args.verbose:
                    raise
                parser.error(err.format(e))

    def start_client(
        self, trn: transport.Transport, parser: argparse.ArgumentParser, args: Args
    ) -> None:
        """Connect to the remote server and execute a command."""
        client = interface.Client(
            trn,
            codec=args.codec,
            retry_count=args.retry_count,
            retry_interval=args.retry_interval,
        )

        # get service metadata
        svcs: list[service.ServiceSpec] | None = None
        try:
            meta = client.service('_meta')

            if args.version:
                # show server status and exit
                status = meta.status()
                self.print_status(status)
                parser.exit()

            svcs = msgspec.convert(meta.services(), list[service.ServiceSpec])

        except errors.RemoteError as e:
            if not args.verbose and e.name == 'KeyError':
                parser.error('metadata service not available')
            raise

        if svcs is None:
            # parser.error exits above, but keep type-checkers happy.
            raise AssertionError('unreachable')

        # add services
        svc_subs = parser.add_subparsers(title='remote services')

        for svc in sorted(svcs, key=lambda s: s.name):
            svc_name = svc.name
            svc_desc = self.get_help(svc.doc)
            svc_parser = svc_subs.add_parser(svc_name, help=svc_desc, description=svc.doc)
            svc_parser.set_defaults(svc_name=svc_name)

            # add service commands
            cmd_subs = svc_parser.add_subparsers(title='commands', dest='command')
            cmd_subs.required = True

            for cmd in svc.commands:
                cmd_name = cmd.name
                cmd_desc = self.get_help(cmd.doc)
                cmd_parser = cmd_subs.add_parser(cmd_name, help=cmd_desc, description=cmd.doc)
                self.add_command_args(cmd_parser, cmd)
                cmd_parser.set_defaults(cmd_name=cmd_name, cmd_meta=cmd)

        # help
        if args.help:
            parser.print_help()
            parser.exit()
        elif not args.rest:
            parser.print_usage()
            parser.exit()

        # select an output formatter
        fmt: Any | None = None
        try:
            fmt = formatter.create(args.format)
        except Exception as e:
            if args.verbose:
                raise
            parser.error(str(e))
        assert fmt is not None

        # get the command arguments
        verbose = args.verbose
        args = parser.parse_args(args.rest)
        cmd_args, cmd_kwargs = self.get_command_args(args)

        # get the command function
        proxy = client.service(args.svc_name, metadata=[args.cmd_meta])
        func = getattr(proxy, args.cmd_name)

        # call the command
        try:
            res = func(*cmd_args, **cmd_kwargs)
            assert res is not None
            fmt.process(res)
        except Exception as e:
            if verbose:
                raise
            log.error('command error: %s', e)

    def start_server(
        self,
        trn: transport.Transport,
        args: Args,
        svc_args: dict[str, dict[str, Any]],
    ) -> None:
        """Start an RPC server with the configured services."""
        # create server
        s = interface.Server(
            trn,
            codec=args.codec,
            version=args.version,
            remote_tracebacks=args.remote_tracebacks,
        )

        # add services
        for name in args.services:
            name, alias = parse_alias(name)
            s_args = svc_args.get(name, {})
            svc = service.create(name, **s_args)
            s.add_service(svc, alias)

        s.serve()

    ## get arguments ##

    def get_prefixed_args(self, args: Args) -> tuple[dict[str, Any], dict[str, Any]]:
        """Split parsed values into transport and service dictionaries."""
        pfx_args: dict[str, dict[str, Any]] = {}

        for name, value in vars(args).items():
            try:
                prefix, cls_name, arg_name = name.split('_', 2)
            except ValueError:
                continue

            cls_args = pfx_args.setdefault(prefix, {})
            cls_args.setdefault(cls_name, {})[arg_name] = value

        return pfx_args.get('transport', {}), pfx_args.get('service', {})

    def get_command_args(self, args: Args) -> tuple[list[Any], dict[str, Any]]:
        """Processes the command-line arguments and returns the arguments to
        pass to the selected command."""
        cmd: SignatureSpec = args.cmd_meta

        cmd_args: list[Any] = []
        cmd_kwargs: dict[str, Any] = {}

        for param in cmd.parameters:
            if param.hide:
                continue

            arg = getattr(args, param.name)
            if param.kind in {Param.POSITIONAL_ONLY, Param.POSITIONAL_OR_KEYWORD}:
                cmd_args.append(arg)
            elif param.kind == Param.VAR_POSITIONAL:
                cmd_args.extend(arg)
            elif param.kind == Param.VAR_KEYWORD:
                cmd_kwargs.update(arg or {})
            elif param.kind == Param.KEYWORD_ONLY:
                cmd_kwargs[param.name] = arg
            else:
                raise AssertionError(f'unsupported argument kind: {param.kind}')

        return cmd_args, cmd_kwargs

    ## add arguments ##

    def add_service_args(self, parser: argparse.ArgumentParser, cls: Any, alias: str) -> None:
        """Expose ``cls.__init__`` parameters under the given service alias."""
        svc_parser = parser.add_argument_group('{} service arguments'.format(alias))

        # add a prefix to every param
        cmd = utils.function.encode(cls.__init__, remove_self=True)
        params = []
        for param in cmd.parameters:
            param = msgspec.structs.replace(
                param,
                name='_'.join(['service', alias, param.name]),
                # force keyword-only params for clarity
                kind=param.kind if param.kind == Param.VAR_KEYWORD else Param.KEYWORD_ONLY,
            )
            if not param.has_default:
                param = msgspec.structs.replace(param, default=argparse.SUPPRESS)
            params.append(param)

        self.add_command_args(svc_parser, cmd, single_flags=False)

    def add_transport_args(
        self, parser: argparse.ArgumentParser, cls: type[transport.Transport]
    ) -> None:
        """Expose transport constructor parameters with a unique prefix."""
        ignored = {'url', 'timeout'}
        trn_name = transport.REGISTRY.get_name(cls)

        trn_parser = parser.add_argument_group(
            '{} transport arguments'.format(trn_name),
            'To see arguments for another transport, set the "--url" argument',
        )

        # add a prefix to every param
        cmd = utils.function.encode(cls.__init__, remove_self=True)
        params = []
        for param in cmd.parameters:
            params.append(
                msgspec.structs.replace(
                    param,
                    name='_'.join(['transport', trn_name, param.name]),
                    # force keyword-only params for clarity
                    kind=param.kind if param.kind == Param.VAR_KEYWORD else Param.KEYWORD_ONLY,
                    hide=param.name in ignored,
                )
            )

        cmd = msgspec.structs.replace(cmd, parameters=tuple(params))

        self.add_command_args(trn_parser, cmd, single_flags=False)

    def add_transport_exception(
        self, parser: argparse.ArgumentParser, name: str, exc: Exception
    ) -> None:
        """Display an error group when a transport fails to import."""
        parser.add_argument_group(
            '{} transport arguments'.format(name),
            'failed to load transport: {}'.format(exc),
        )

    def add_command_args(self, parser: Any, cmd: SignatureSpec, single_flags: bool = True) -> None:
        """Translate command metadata into argparse arguments."""

        def is_option_arg(param: ParameterSpec) -> bool:
            return param.kind == Param.VAR_KEYWORD or param.has_default

        if single_flags:
            # keep track of used single char flags
            chars = set('h')
            # include single char arguments
            chars.update(
                p.name for p in cmd.parameters if len(p.name) == 1 and not is_option_arg(p)
            )
        else:
            chars = None

        for param in cmd.parameters:
            name = param.name
            kind = param.kind
            hint = param.annotation
            doc = param.doc

            if param.hide:
                continue

            kwargs: dict[str, Any] = {'metavar': name}

            if param.has_default:
                kwargs['default'] = param.default

            if kind in {Param.KEYWORD_ONLY, Param.VAR_KEYWORD}:  # **kwargs
                self.add_option_arg(parser, param, chars)

            elif param.has_default:  # args with defaults
                self.add_option_arg(parser, param, chars)

            else:  # positional args
                if kind == Param.VAR_POSITIONAL:  # *args
                    kwargs['nargs'] = '*'

                kwargs.update(
                    {
                        'type': self.get_converter(hint),
                        'help': self.get_argument_help(doc, hint, param.default),
                    }
                )
                parser.add_argument(name, **kwargs)

    def add_option_arg(
        self, parser: Any, param: ParameterSpec, chars: set[str] | None = None
    ) -> None:
        """Add an individual option flag, handling bool/kwargs special cases."""
        name = param.name
        kind = param.kind
        hint = param.annotation
        doc = param.doc
        default = param.default

        # use dashes instead of underscores for param names
        flag_name = name.replace('_', '-')

        # check for possible short flags
        flags = []
        added = False
        c = flag_name[0]
        C = c.upper()

        # check if the lower or uppercase char is unique
        if not chars:
            # don't add a short flag
            pass
        elif c not in chars:
            flags.append('-' + c)
            chars.add(c)
            added = True
        elif C not in chars:
            flags.append('-' + C)
            chars.add(C)
            added = True

        # add a long flag if no short flag was added
        # add a long flag if the name is more than 1 character
        if not added or len(flag_name) > 1:
            flags.append('--' + flag_name)

        if hint == 'bool':
            # handle bool special case
            group = parser.add_mutually_exclusive_group()
            if not default:
                # in case default is None
                default = False

            help = self.get_argument_help(doc)

            # add a flag for the True value
            group.add_argument(
                *flags,
                action='store_true',
                default=default,
                dest=name,
                help=help + ' (default)' if default is True else '',
            )

            # add a flag for the False value
            group.add_argument(
                '--no-' + flag_name,
                action='store_false',
                dest=name,
                help=help + ' (default)' if default is False else '',
            )

        elif kind == Param.VAR_KEYWORD:
            parser.add_argument(
                *flags,
                action='append',
                dest=name,
                type=self.get_converter('keyword'),
                metavar='name=value',
                default=default,
                help=self.get_argument_help(doc, None, default),
            )

        else:
            parser.add_argument(
                *flags,
                dest=name,
                type=self.get_converter(hint),
                metavar=self.get_argument_hint(hint),
                default=default,
                help=self.get_argument_help(doc, None, default),
            )

    def add_global_args(self, parser: argparse.ArgumentParser) -> None:
        """Adds an argument group to *parser* for global arguments."""

        egroup = parser.add_mutually_exclusive_group()
        egroup.add_argument(
            '-C',
            '--client',
            action='store_false',
            dest='server_mode',
            help='start in client mode (default)',
            default=False,
        )
        egroup.add_argument(
            '-S', '--server', action='store_true', dest='server_mode', help='start in server mode'
        )

        parser.add_argument(
            '-l',
            '--list',
            choices=['codecs', 'formatters', 'services', 'transports'],
            help='list the modules available for the selected category',
        )
        parser.add_argument(
            '-v',
            '--verbose',
            action='count',
            default=0,
            help='enable verbose output (-vv for more)',
        )
        parser.add_argument(
            '-V',
            '--version',
            nargs='?',
            const=True,
            help='show server version (client) or set server version (server)',
        )

        group = parser.add_argument_group('configuration arguments')

        group.add_argument(
            '-u',
            '--url',
            type=utils.url.Url,
            default=utils.DEFAULT_URL,
            metavar='TRANSPORT://HOST:PORT',
            help='URL to connect or bind to (default: {})'.format(utils.DEFAULT_URL),
        )
        group.add_argument(
            '-i',
            '--import',
            action='append',
            dest='imports',
            metavar='IMPORT',
            default=[],
            help='import an additional (codec/formatter/service/transport) module',
        )
        group.add_argument(
            '-c',
            '--codec',
            help='the codec format to use (default: {} on server)'.format(interface.DEFAULT_CODEC),
        )
        group.add_argument(
            '-s',
            '--service',
            action='append',
            dest='services',
            metavar='SERVICE[:alias]',
            default=[],
            help='register a service with the server (can be set multiple times)',
        )

        group = parser.add_argument_group('client arguments')

        group.add_argument(
            '-t',
            '--timeout',
            type=float,
            help='number of seconds to wait for a response (default: no timeout)',
        )
        group.add_argument(
            '-r',
            '--retry-count',
            type=int,
            help='number of retry attempts to make (-1 for unlimited, default: no retries)',
        )
        group.add_argument(
            '--retry-interval',
            type=float,
            help='number of seconds between retry attempts (default: 1.0)',
        )

        group = parser.add_argument_group('server arguments')

        group.add_argument(
            '--remote-tracebacks', action='store_true', help='send tracebacks with errors'
        )

        group = parser.add_argument_group('output arguments')

        format_default = {
            'piped': 'json',
            'redirected': 'raw',
            'terminal': 'pretty',
        }[io_stat_mode()]
        group.add_argument(
            '-f',
            '--format',
            default=format_default,
            help='select a formatter by name or provide a custom Formatter '
            "subclass (default: 'pretty' on terminals, "
            "'json' when piped, and 'raw' when redirected)",
        )

    ## parser help ##

    def get_help(self, doc: str | None) -> str:
        """Return the first line of a documentation string."""
        doc = doc or '\n'
        return doc.splitlines()[0]

    def get_argument_help(
        self, doc: str | None = None, hint: str | None = None, default: Any = None
    ) -> str:
        """Build an argparse help string that includes hints and defaults."""
        if is_stream_hint(hint):
            hint = "path or '-' for stdin"
        help = '<{}>'.format(hint) if hint else ''
        if doc:
            help = '{} {}'.format(doc, help)
        if default not in [Param.empty, argparse.SUPPRESS, None]:
            help += ' (default: {})'.format(default)
        return help

    def get_argument_hint(self, hint: str | None) -> str:
        """Return a placeholder string usable as metavar text."""
        if not hint:
            return '<str>'
        elif hint in COLLECTION_TYPES:
            return '<path or JSON>'
        else:
            return '<{}>'.format(hint)

    ## parser utils ##

    def get_converter(self, hint: str | None) -> Callable[[str], Any]:
        """Returns a type converter keyed to a specific typehint."""
        if hint == 'int':

            def conv(value: str) -> Any:
                return int(value)
        elif hint == 'float':

            def conv(value: str) -> Any:
                return float(value)
        elif hint == 'bytes':

            def conv(value: str) -> Any:
                return value.encode()
        elif is_stream_hint(hint):

            def conv(value: str) -> Any:
                fp = cast(BinaryIO, argparse.FileType('rb')(value))
                return utils.path.iter_file(fp)
        elif hint == 'keyword':

            def conv(value: str) -> Any:
                return value.split('=', 1)
        elif hint == 'datetime':

            def conv(value: str) -> Any:
                try:
                    return datetime.datetime.strptime(value, DATETIME_FORMAT)
                except ValueError:
                    try:
                        return datetime.datetime.strptime(value, DATE_FORMAT)
                    except Exception:
                        return datetime.datetime.combine(
                            datetime.date.today(),
                            datetime.datetime.strptime(value, TIME_FORMAT).time(),
                        )
        elif hint == 'stream':

            def conv(value: str) -> Any:
                return (x for x in value)
        elif hint in COLLECTION_TYPES:

            def conv(value: str) -> Any:
                try:
                    with open(value) as f:
                        return json.load(f)
                except Exception:
                    return json.loads(value)
        else:

            def conv(value: str) -> Any:
                return value

        # the converter name is used in error messages
        conv.__name__ = hint or 'str'

        return conv

    def print_status(self, status: dict[str, Any]) -> None:
        """Prints the server version and status data."""
        # TODO: abide by --format flag
        width = max(len(k) for k in status)
        for k, v in sorted(status.items()):
            print('{:>{}}: {}'.format(k, width, v or '-'))


##
## cli utils
##


def parse_alias(name: str) -> tuple[str, str | None]:
    """Split ``name`` into ``module`` and ``alias`` if ``:`` is present."""
    try:
        base, alias = name.split(':')
    except ValueError:
        return name, None
    return base, alias


def is_stream_hint(hint: str | None) -> bool:
    return False if hint is None else hint.startswith(('Generator', 'Iterable', 'Iterator'))


def io_stat_mode() -> str:
    """Return whether stdout is piped, redirected, or connected to a tty."""
    mode = os.fstat(sys.stdout.fileno()).st_mode
    if stat.S_ISFIFO(mode):
        return 'piped'
    elif stat.S_ISREG(mode):
        return 'redirected'
    else:
        return 'terminal'
