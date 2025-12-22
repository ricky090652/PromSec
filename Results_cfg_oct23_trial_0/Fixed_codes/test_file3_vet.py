import os

def calculate_total(input_list):
    try:
        total = sum(input_list)
        return total
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Example usage
input_list = [1, 2, 3, 4, 5]
result = calculate_total(input_list)
print(result)