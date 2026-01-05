import csv

def read_and_print_first_n_lines(file_path, num_lines=5):
    """
    Reads a CSV file and prints the first N lines.

    Args:
        file_path (str): The path to the CSV file.
        num_lines (int): The number of lines to print. Defaults to 5.
    """
    try:
        with open(file_path, mode='r', newline='', encoding='utf-8') as file:
            csv_reader = csv.reader(file)
            print(f"Reading first {num_lines} lines from '{file_path}':")
            for i, row in enumerate(csv_reader):
                if i < num_lines:
                    print(row)
                else:
                    break
    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    csv_file = "sample.csv"  # You can change this to your CSV file name
    read_and_print_first_n_lines(csv_file, 5)
