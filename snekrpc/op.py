from __future__ import annotations


class Op:
    handshake = 0  # <raw> initial handshake (codec)
    command = 1  # call a command (svc_name, cmd_name, args, kwargs)
    data = 2  # return data (data)
    error = 3  # return error (name, msg, tb)
    stream_start = 4  # start of stream ([name])
    stream_end = 5  # end of stream

    @classmethod
    def to_str(cls, op: int) -> str:
        for name, value in vars(cls).items():
            if value == op:
                return name
        raise ValueError(f'invalid op code: {op}')
