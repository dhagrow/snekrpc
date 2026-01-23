from client import Client, Event


def main():
    c = Client(':1234')
    svc = c.example

    print(f'{svc.echo("ping")=}')

    print(f'{svc.event()=}')

    for event in svc.events():
        print(f'{Event(**event)=}')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
