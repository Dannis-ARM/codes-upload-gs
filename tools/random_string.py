import random
import string

def generate_random_string(length: int) -> str:
    """
    Generates a random string of a specified length.

    The string contains a mix of lowercase letters, uppercase letters,
    and digits.

    Args:
        length: The desired length of the random string.

    Returns:
        A randomly generated string.
    """
    # Define the pool of characters to choose from
    characters = string.ascii_letters + string.digits
    
    # Use random.choice() to pick a character for each position in the string.
    # The list comprehension creates a list of random characters, and
    # ''.join() efficiently concatenates them into a single string.
    random_string = ''.join(random.choice(characters) for _ in range(length))
    
    return random_string

# --- Example Usage ---

# Generate a random string of length 10
random_str_10 = generate_random_string(10)
print(f"Random string of length 10: {random_str_10}")

# Generate a random string of length 20
random_str_20 = generate_random_string(20)
print(f"Random string of length 20: {random_str_20}")
