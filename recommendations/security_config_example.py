from cryptography.fernet import Fernet


# Input sanitization
def sanitize_user_input(user_input: str, max_length: int = 1000) -> str:
    """Sanitize user input to prevent issues."""
    if not isinstance(user_input, str):
        raise TypeError("Input must be a string")
    
    # Basic length check
    if len(user_input) > max_length:
        raise ValueError(f"Input too long (max {max_length} characters)")
    
    # Remove null bytes and control characters (except newlines/tabs)
    sanitized = ''.join(
        char for char in user_input 
        if char.isprintable() or char in '\n\t'
    )
    
    return sanitized.strip()