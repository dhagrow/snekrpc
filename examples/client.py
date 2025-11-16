import snekrpc
from snekrpc import logs


def main():
    logs.init()

    c = snekrpc.Client('tcp://localhost:1234')
    print(c.service_names())

    s = c.service('ex')
    print(s.echo('asdf'))

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
