import os

def calculate_average(numbers):
    try:
        if not numbers:
            raise ValueError("Empty list")
        
        total = 0
        count = 0
        for num in numbers:
            if not isinstance(num, (int, float)):
                raise ValueError("Non-numeric value in the list")
            total += num
            count += 1
        
        return total / count
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

numbers = [1, 2, 3, 4, 5]
average = calculate_average(numbers)
print(average)