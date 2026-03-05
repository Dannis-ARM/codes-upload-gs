import subprocess
import json
import argparse
import sys

class AttrDict(dict):
    """
    A helper class to allow accessing dictionary keys as attributes (a.b.c).
    """
    def __init__(self, d):
        for key, value in d.items():
            # Recursively handle nested dictionaries and lists
            if isinstance(value, dict):
                value = AttrDict(value)
            elif isinstance(value, list):
                value = [AttrDict(i) if isinstance(i, dict) else i for i in value]
            self[key] = value

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(f"No such attribute: {item}")

def get_podman_inspect(target):
    """
    Runs podman inspect and returns the raw JSON data.
    """
    try:
        # Use subprocess to run the command
        result = subprocess.run(
            ['podman', 'inspect', target],
            capture_output=True,
            text=True,
            check=True
        )
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to inspect '{target}'. {e.stderr.strip()}")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: Failed to parse JSON output from podman.")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'podman' command not found. Please ensure Podman is installed.")
        sys.exit(1)

def convert_to_object(data):
    """
    Converts the first element of inspect list into an AttrDict object.
    """
    if not data or not isinstance(data, list):
        return None
    # Podman inspect always returns a list, we take the first item
    return AttrDict(data[0])

def main():
    # Setup argparse to support image ID or URL/Name
    parser = argparse.ArgumentParser(description="Inspect a Podman image and access data via attributes.")
    parser.add_argument("image", help="The Image ID or Image URL (Name) to inspect.")
    
    args = parser.parse_args()

    # 1. Fetch data
    raw_data = get_podman_inspect(args.image)

    # 2. Convert to object
    image_obj = convert_to_object(raw_data)

    if image_obj:
        # Example Usage:
        print(f"Successfully inspected: {image_obj.Id}")
        
        # Demonstrating a.b.c.d access (common podman fields)
        try:
            # Note: Podman keys are often capitalized (e.g., Config.Hostname)
            if hasattr(image_obj, 'Config'):
                print(f"Architecture: {image_obj.Architecture}")
                print(f"OS: {image_obj.Os}")
                print(f"Author: {image_obj.Author}")
        except AttributeError as e:
            print(f"Attribute access error: {e}")
    else:
        print("No data found for the given image.")

if __name__ == "__main__":
    main()