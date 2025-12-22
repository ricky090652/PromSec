import os

def get_unique_elements(input_list):
    unique_elements = []
    for num in input_list:
        if num not in unique_elements:
            unique_elements.append(num)
    return unique_elements

# Example usage
input_list = [1, 2, 3, 3, 4, 5, 5, 6]
result = get_unique_elements(input_list)
print(result)