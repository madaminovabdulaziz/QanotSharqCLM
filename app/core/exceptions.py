# app/core/exceptions.py

class NotFoundException(Exception):
    """Entity not found"""
    pass

class ValidationException(Exception):
    """Validation failed"""
    pass

class PermissionDeniedException(Exception):
    """Permission denied"""
    pass

class BusinessRuleException(Exception):
    """Business rule violation"""
    pass


class TokenExpiredException(Exception):
    pass

class TokenAlreadyUsedException(Exception):
    pass


class InvalidStatusTransitionException(Exception):
    pass