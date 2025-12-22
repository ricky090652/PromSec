import os

def calculate_total(numbers):
    try:
        total = sum(numbers)
        return total
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

numbers = [1, 2, 3, 4, 5]
result = calculate_total(numbers)
print(result)