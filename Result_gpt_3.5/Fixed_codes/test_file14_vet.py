import os

def calculate_total(prices, discount_percentage):
    try:
        discount = float(discount_percentage) / 100
        total = sum([float(price) * (1 - discount) for price in prices])
        return total
    except Exception as e:
        print(f"An error occurred: {e}")
        return None

# Example usage
prices = [10, 20, 30]
discount_percentage = os.getenv("DISCOUNT_PERCENTAGE")
total_price = calculate_total(prices, discount_percentage)
print(f"Total price after discount: {total_price}")