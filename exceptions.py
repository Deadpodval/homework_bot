class EmptyAPIResponseError(Exception):
    pass


class SendMessageError(Exception):
    pass


class ServerConnectionError(Exception):
    pass


class ParseStatusError(Exception):
    pass


class GlobalException(Exception):
    pass

class TokenNotFoundError(Exception):
    pass
