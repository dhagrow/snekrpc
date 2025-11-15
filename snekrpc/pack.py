import argparse
import os
import pkgutil
import zipfile

from . import logs

SHELL_HEADER = b'#! /usr/bin/env python\n'
MAIN = b'from snekrpc import __main__;__main__.main()'
EXCLUDE = frozenset(['__pycache__'])

PACKAGES = frozenset(['msgpack', 'temporenc'])

log = logs.get(__name__)


def exclude(name):
    if name.startswith('.'):
        return True
    elif name.endswith(('.pyc', '.so')):
        return True
    elif name in EXCLUDE:
        return True
    return False


def collect_source(root_path):
    dst_root_path = os.path.dirname(root_path)

    for dpath, dnames, fnames in os.walk(root_path):
        dnames[:] = [dname for dname in dnames if not exclude(dname)]

        for fname in fnames:
            if exclude(fname):
                continue

            src_path = os.path.join(dpath, fname)
            rpath = os.path.relpath(dpath, dst_root_path)
            dst_path = os.path.join(rpath, fname)

            yield src_path, dst_path


def pack(root_path, output_path, services, compresslevel):
    paths = list(collect_source(root_path))

    for package in PACKAGES:
        modpath = pkgutil.get_loader(package).get_filename()
        paths += list(collect_source(os.path.dirname(modpath)))

    for service in services:
        modpath = pkgutil.get_loader(service).get_filename()
        modname = os.path.basename(modpath)
        paths.append((modpath, os.path.join('snekrpc/service', modname)))

    with open(output_path, 'wb') as fp:
        fp.write(SHELL_HEADER)

        log.debug('compression level set to: %s', compresslevel)
        zfp = zipfile.ZipFile(fp, 'a', zipfile.ZIP_DEFLATED, compresslevel=compresslevel)
        with zfp:
            fpath = '__main__.py'
            log.debug('adding: %s', fpath)
            zfp.writestr(fpath, MAIN)

            for src_path, dst_path in sorted(paths):
                log.debug('adding: %s', dst_path)
                zfp.write(src_path, dst_path)

    os.chmod(output_path, 0o744)
    log.info('packed script written to: %s', output_path)


def add_arguments(parser):
    parser.add_argument('output', help='path for the output file')
    parser.add_argument(
        '-s',
        '--service',
        action='append',
        dest='services',
        default=[],
        help='a service module to include (can be set multiple times)',
    )
    parser.add_argument(
        '-c',
        '--compression-level',
        type=int,
        default=0,
        help='level of compression to apply (0-9) (default: %(default)s)',
    )
    parser.add_argument('-v', '--verbose', action='count', default=0, help='enable verbose output')


def main():
    parser = argparse.ArgumentParser()
    add_arguments(parser)

    args = parser.parse_args()

    logs.init(args.verbose)

    pack('./snekrpc', args.output, args.services, args.compression_level)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
