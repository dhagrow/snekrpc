from .client import Client, Command


def main():
    c = Client(':1234')
    svc = c.example

    print(f'{svc.echo("ping")=}')

    svc.command(Command('asdf', {'a': 1}))

    print(f'{svc.event()=}')

    for event in svc.events():
        print(f'[{event.name}] {event.message}')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
