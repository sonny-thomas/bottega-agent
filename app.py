# Standard library imports
from datetime import datetime
import getpass
import os
from typing import Annotated, Dict, List, Literal, Optional
import uuid
import logging

# Third-party imports
from dotenv import load_dotenv
import pandas as pd
import sqlite3
from typing_extensions import TypedDict

# Langchain imports
from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import ToolMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_core.runnables import RunnableLambda
from langchain.tools import tool

# Langgraph imports
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# Twilio import
from twilio.rest import Client

# Flask imports
from flask import Flask, request, Response, stream_with_context, jsonify, session, send_from_directory, render_template, url_for, render_template, Blueprint
from flask_cors import CORS
import uuid
import json

# Stripe imports
import os
import stripe
from stripe.error import StripeError
from datetime import datetime
import logging

# Load environment variables from .env file
load_dotenv()

#Twilio credentials

twilio_phone_number = "+18336102490"

restaurant_phone_number = "+15305649326"

client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]

# Function to send SMS
def send_sms(to, body):
    message = client.messages.create(
        body=body,
        from_=twilio_phone_number,
        to=to
    )
    return message.sid

# Database connection
DB_NAME = 'bottega_customer_chatbot.db'

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# Define tools

import re

def standardize_phone_number(phone: str) -> str:
    """
    Standardize the phone number to +1XXXXXXXXXX format.
    Assumes US phone numbers.
    """
    digits = re.sub(r'\D', '', phone)
    if (len(digits) == 11 and digits.startswith('1')) or len(digits) == 10:
        if len(digits) == 10:
            digits = '1' + digits
        return f"+{digits}"
    else:
        raise ValueError("Invalid phone number format")
    
@tool
def create_or_update_customer(name: str, phone: str, address: Optional[str] = None) -> str:
    """
    Create a new customer or update existing one based on phone number.
    Phone number will be standardized to (+1XXXXXXXXXX) format.
    Address is optional.
    """
    try:
        standardized_phone = standardize_phone_number(phone)
    except ValueError:
        return "Error: Invalid phone number format. Please provide a valid US phone number."

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT CustomerID FROM Customers WHERE Phone = ?", (standardized_phone,))
        existing_customer = cursor.fetchone()

        if existing_customer:
            customer_id = existing_customer['CustomerID']
            if address:
                cursor.execute("""
                    UPDATE Customers
                    SET Name = ?, Address = ?
                    WHERE CustomerID = ?
                """, (name, address, customer_id))
            else:
                cursor.execute("""
                    UPDATE Customers
                    SET Name = ?
                    WHERE CustomerID = ?
                """, (name, customer_id))
            message = f"Customer information updated. Customer ID: {customer_id}"
        else:
            if address:
                cursor.execute("""
                    INSERT INTO Customers (Name, Phone, Address)
                    VALUES (?, ?, ?)
                """, (name, standardized_phone, address))
            else:
                cursor.execute("""
                    INSERT INTO Customers (Name, Phone)
                    VALUES (?, ?)
                """, (name, standardized_phone))
            customer_id = cursor.lastrowid
            message = f"New customer created. Customer ID: {customer_id}"

        conn.commit()
        return message

# Update Customer Address tool
@tool
def update_customer_address(customer_id: int, address: str) -> str:
    """Update the address for an existing customer."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Customers
            SET Address = ?
            WHERE CustomerID = ?
        """, (address, customer_id))
        conn.commit()
        if cursor.rowcount > 0:
            return f"Address updated successfully for customer ID: {customer_id}"
        else:
            return f"No customer found with ID: {customer_id}"
        
# Check Customer Exists tool        
@tool
def check_customer_exists(phone: str) -> bool:
    """Check if a customer exists based on phone number."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM Customers WHERE Phone = ?", (phone,))
        return cursor.fetchone() is not None

# Fetch Customer Orders tool
@tool
def fetch_customer_orders(customer_id: int) -> List[Dict]:
    """Fetch all previous orders for a given customer."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT *
            FROM Orders o
            WHERE o.CustomerID = ?
            ORDER BY o.OrderDate DESC
        """, (customer_id,))
        return [dict(row) for row in cursor.fetchall()]

# Get Menu Categories tool
@tool
def get_menu_categories() -> List[Dict]:
    """Fetch all menu categories."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM MenuCategories")
        return [dict(row) for row in cursor.fetchall()]

# Get Menu Items tool
@tool
def get_menu_items(category_id: Optional[int] = None) -> List[Dict]:
    """Fetch menu items, optionally filtered by category, including configurations and add-ons."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if category_id:
            cursor.execute("""
                SELECT m.*, c.CategoryName
                FROM MenuItems m
                JOIN MenuCategories c ON m.CategoryID = c.CategoryID
                WHERE m.CategoryID = ?
            """, (category_id,))
        else:
            cursor.execute("""
                SELECT m.*, c.CategoryName
                FROM MenuItems m
                JOIN MenuCategories c ON m.CategoryID = c.CategoryID
            """)
        items = [dict(row) for row in cursor.fetchall()]
        
        for item in items:
            cursor.execute("SELECT * FROM MenuConfigurations WHERE ItemID = ?", (item['ItemID'],))
            item['configurations'] = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("SELECT * FROM MenuAddOns WHERE ItemID = ?", (item['ItemID'],))
            item['addons'] = [dict(row) for row in cursor.fetchall()]
        
        return items


# Add to Cart tool    
@tool
def add_to_cart(customer_id: int, item_id: int, quantity: int, special_instructions: Optional[str] = None, configuration_id: Optional[int] = None, addon_id: Optional[int] = None) -> str:
    """Add an item to the customer's cart with optional configuration, add-on, and special instructions."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT CartID FROM Cart WHERE CustomerID = ? ORDER BY CreatedAt DESC LIMIT 1", (customer_id,))
            cart = cursor.fetchone()

            if not cart:
                cursor.execute("INSERT INTO Cart (CustomerID) VALUES (?)", (customer_id,))
                cart_id = cursor.lastrowid
            else:
                cart_id = cart['CartID']

            cursor.execute("""
                INSERT INTO CartItems (CartID, ItemID, Quantity, SpecialInstructions, ConfigurationID, AddOnID)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(CartID, ItemID, ConfigurationID, AddOnID) DO UPDATE SET 
                Quantity = Quantity + excluded.Quantity,
                SpecialInstructions = COALESCE(excluded.SpecialInstructions, CartItems.SpecialInstructions)
            """, (cart_id, item_id, quantity, special_instructions, configuration_id, addon_id))

            conn.commit()
            return f"Successfully added {quantity} of item {item_id} to the cart. Configuration ID: {configuration_id}, Add-on ID: {addon_id}, Special instructions: {special_instructions or 'None'}"
        except sqlite3.Error as e:
            conn.rollback()
            return f"Error adding item to cart: {e}"


# View Cart tool
@tool
def view_cart(customer_id: int) -> List[Dict]:
    """Fetch items in the customer's cart, including configurations and add-ons."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ci.CartItemID, mi.ItemName, ci.Quantity, mi.SellingPrice, ci.SpecialInstructions,
                   mc.Configuration, mc.Price as ConfigurationPrice,
                   ma.AddOn, ma.Price as AddOnPrice
            FROM CartItems ci
            JOIN Cart c ON ci.CartID = c.CartID
            JOIN MenuItems mi ON ci.ItemID = mi.ItemID
            LEFT JOIN MenuConfigurations mc ON ci.ConfigurationID = mc.ConfigurationID
            LEFT JOIN MenuAddOns ma ON ci.AddOnID = ma.AddOnID
            WHERE c.CustomerID = ?
            ORDER BY ci.CartItemID
        """, (customer_id,))
        return [dict(row) for row in cursor.fetchall()]

# Place order tool
@tool
def place_order(customer_id: int, order_type: str) -> str:
    """Place an order for the customer, including configurations, add-ons, and special instructions, and generate a Stripe payment link."""
    logging.info(f"Starting place_order for customer_id: {customer_id}, order_type: {order_type}")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            # Fetch cart and order details
            cursor.execute("SELECT CartID FROM Cart WHERE CustomerID = ? ORDER BY CreatedAt DESC LIMIT 1", (customer_id,))
            cart = cursor.fetchone()
            if not cart:
                return "Error: No active cart found for the customer."
            cart_id = cart['CartID']

            # Fetch order items and total amount
            cursor.execute("""
                SELECT mi.ItemName, ci.Quantity, 
                       (ci.Quantity * (mi.SellingPrice + COALESCE(mc.Price, 0) + COALESCE(ma.Price, 0))) as ItemTotal, 
                       ci.SpecialInstructions, mc.Configuration, ma.AddOn
                FROM CartItems ci
                JOIN MenuItems mi ON ci.ItemID = mi.ItemID
                LEFT JOIN MenuConfigurations mc ON ci.ConfigurationID = mc.ConfigurationID
                LEFT JOIN MenuAddOns ma ON ci.AddOnID = ma.AddOnID
                WHERE ci.CartID = ?
            """, (cart_id,))
            order_items = cursor.fetchall()

            cursor.execute("""
                SELECT SUM(ci.Quantity * (mi.SellingPrice + COALESCE(mc.Price, 0) + COALESCE(ma.Price, 0))) as TotalAmount
                FROM CartItems ci
                JOIN MenuItems mi ON ci.ItemID = mi.ItemID
                LEFT JOIN MenuConfigurations mc ON ci.ConfigurationID = mc.ConfigurationID
                LEFT JOIN MenuAddOns ma ON ci.AddOnID = ma.AddOnID
                WHERE ci.CartID = ?
            """, (cart_id,))
            total_amount = cursor.fetchone()['TotalAmount']

            # Create the order in the database
            cursor.execute("""
                INSERT INTO Orders (CustomerID, CartID, TotalAmount, OrderType)
                VALUES (?, ?, ?, ?)
            """, (customer_id, cart_id, total_amount, order_type))
            order_id = cursor.lastrowid

            # Insert order items
            cursor.execute("""
                INSERT INTO OrderItems (OrderID, ItemID, Quantity, Price, SpecialInstructions, ConfigurationID, AddOnID)
                SELECT ?, ci.ItemID, ci.Quantity, 
                       (mi.SellingPrice + COALESCE(mc.Price, 0) + COALESCE(ma.Price, 0)),
                       ci.SpecialInstructions, ci.ConfigurationID, ci.AddOnID
                FROM CartItems ci
                JOIN MenuItems mi ON ci.ItemID = mi.ItemID
                LEFT JOIN MenuConfigurations mc ON ci.ConfigurationID = mc.ConfigurationID
                LEFT JOIN MenuAddOns ma ON ci.AddOnID = ma.AddOnID
                WHERE ci.CartID = ?
            """, (order_id, cart_id))

            # Set initial order status
            cursor.execute("INSERT INTO OrderStatus (OrderID, Status) VALUES (?, 'Pending')", (order_id,))
            
            # Clear the cart
            cursor.execute("DELETE FROM CartItems WHERE CartID = ?", (cart_id,))

            # Commit the transaction
            conn.commit()

            # Fetch customer details
            cursor.execute("SELECT Name, Phone, Address FROM Customers WHERE CustomerID = ?", (customer_id,))
            customer = cursor.fetchone()

            # Prepare order details string
            order_details = "\n".join([
                f"- {item['ItemName']} x{item['Quantity']} (${item['ItemTotal']:.2f})"
                f"{' - Configuration: ' + item['Configuration'] if item['Configuration'] else ''}"
                f"{' - Add-on: ' + item['AddOn'] if item['AddOn'] else ''}"
                f"{' - Special Instructions: ' + item['SpecialInstructions'] if item['SpecialInstructions'] else ''}"
                for item in order_items
            ])

            # Generate Stripe Payment Link
            try:
                logging.info(f"Creating Stripe Price for order {order_id}")
                price = stripe.Price.create(
                    unit_amount=int(total_amount * 100),  # Convert to cents
                    currency="usd",
                    product_data={
                        "name": f"Order #{order_id} - Bottega Restaurant",
                    },
                )
                logging.info(f"Stripe Price created successfully: {price.id}")

                logging.info(f"Creating Stripe Payment Link for order {order_id}")
                payment_link = stripe.PaymentLink.create(
                    line_items=[{
                        "price": price.id,
                        "quantity": 1,
                    }],
                    after_completion={
                        "type": "redirect",
                        "redirect": {"url": f"https://yourwebsite.com/order-confirmation/{order_id}"}
                    },
                    metadata={
                        "order_id": str(order_id),
                        "customer_id": str(customer_id),
                        "order_type": order_type,
                    },
                )
                payment_url = payment_link.url
                logging.info(f"Stripe Payment Link created successfully: {payment_url}")
            except stripe.error.StripeError as e:
                logging.error(f"Stripe error occurred: {str(e)}")
                logging.error(f"Error type: {type(e).__name__}")
                if hasattr(e, 'code'):
                    logging.error(f"Error code: {e.code}")
                if hasattr(e, 'param'):
                    logging.error(f"Error parameter: {e.param}")
                if hasattr(e, 'http_status'):
                    logging.error(f"HTTP status: {e.http_status}")
                payment_url = "Error generating payment link. Please contact support."
            except Exception as e:
                logging.error(f"Unexpected error in Stripe operations: {str(e)}")
                logging.error(f"Error type: {type(e).__name__}")
                payment_url = "Unexpected error. Please contact support."

            # Prepare and send customer message
            customer_message = f"""
Dear {customer['Name']},

Thank you for your order with Bottega Restaurant!

Order Details:
Order ID: {order_id}
Date & Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Type: {order_type.capitalize()}

Items:
{order_details}

Total Amount: ${total_amount:.2f}

To complete your order, please use this secure payment link:
{payment_url}

Your order will be prepared once payment is received.

"""
            if order_type.lower() == 'delivery':
                if customer['Address']:
                    customer_message += f"Delivery Address: {customer['Address']}\n"
                else:
                    customer_message += "We'll contact you to confirm your delivery address.\n"
            else:
                customer_message += "This is a pickup order. Please collect your order from our restaurant.\n"

            customer_message += """
For any questions, please contact us @ +15305649326.

Thank you for choosing Bottega Restaurant!
"""
            sms_result = send_sms(customer['Phone'], customer_message)
            if not sms_result:
                logging.warning(f"Failed to send SMS to customer {customer_id}")

            # Prepare and send restaurant message
            restaurant_message = f"""
New Order Alert!

Order ID: {order_id}
Customer: {customer['Name']}
Phone: {customer['Phone']}
Type: {order_type.capitalize()}
Date & Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Items:
{order_details}

Total Amount: ${total_amount:.2f}

"""
            if order_type.lower() == 'delivery':
                if customer['Address']:
                    restaurant_message += f"Delivery Address: {customer['Address']}\n"
                else:
                    restaurant_message += "Address not provided. Please contact customer for delivery details.\n"
            else:
                restaurant_message += "This is a pickup order.\n"

            restaurant_message += f"Please prepare this order for {order_type} once payment is confirmed."

            sms_result = send_sms(restaurant_phone_number, restaurant_message)
            if not sms_result:
                logging.warning("Failed to send SMS to restaurant")

            return f"""Order placed successfully. 
Order ID: {order_id}
Total Amount: ${total_amount:.2f}
Payment Link: {payment_url}

Please inform the customer that their order will be prepared once payment is received."""

        except sqlite3.Error as e:
            conn.rollback()
            logging.error(f"SQLite error: {str(e)}")
            return f"Error placing order: {e}"
        except Exception as e:
            conn.rollback()
            logging.error(f"Unexpected error in place_order: {str(e)}")
            return f"Unexpected error placing order. Please try again or contact support."


@tool
def update_cart_item(customer_id: int, cart_item_id: int, new_quantity: Optional[int] = None, new_special_instructions: Optional[str] = None, new_configuration_id: Optional[int] = None, new_addon_id: Optional[int] = None) -> str:
    """Update the quantity, special instructions, configuration, or add-on of an item in the customer's cart, or remove the item if quantity is set to 0."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT ci.CartItemID, ci.Quantity, ci.SpecialInstructions, mi.ItemName,
                       mc.Configuration, ma.AddOn
                FROM CartItems ci
                JOIN Cart c ON ci.CartID = c.CartID
                JOIN MenuItems mi ON ci.ItemID = mi.ItemID
                LEFT JOIN MenuConfigurations mc ON ci.ConfigurationID = mc.ConfigurationID
                LEFT JOIN MenuAddOns ma ON ci.AddOnID = ma.AddOnID
                WHERE c.CustomerID = ? AND ci.CartItemID = ?
            """, (customer_id, cart_item_id))
            cart_item = cursor.fetchone()

            if not cart_item:
                return f"Error: Cart item {cart_item_id} not found for this customer."

            if new_quantity is not None:
                if new_quantity == 0:
                    cursor.execute("DELETE FROM CartItems WHERE CartItemID = ?", (cart_item_id,))
                    conn.commit()
                    return f"Item '{cart_item['ItemName']}' has been removed from your cart."
                else:
                    cursor.execute("UPDATE CartItems SET Quantity = ? WHERE CartItemID = ?", (new_quantity, cart_item_id))

            if new_special_instructions is not None:
                cursor.execute("UPDATE CartItems SET SpecialInstructions = ? WHERE CartItemID = ?", (new_special_instructions, cart_item_id))

            if new_configuration_id is not None:
                cursor.execute("UPDATE CartItems SET ConfigurationID = ? WHERE CartItemID = ?", (new_configuration_id, cart_item_id))

            if new_addon_id is not None:
                cursor.execute("UPDATE CartItems SET AddOnID = ? WHERE CartItemID = ?", (new_addon_id, cart_item_id))

            conn.commit()

            cursor.execute("""
                SELECT ci.Quantity, ci.SpecialInstructions, mi.ItemName,
                       mc.Configuration, ma.AddOn
                FROM CartItems ci
                JOIN MenuItems mi ON ci.ItemID = mi.ItemID
                LEFT JOIN MenuConfigurations mc ON ci.ConfigurationID = mc.ConfigurationID
                LEFT JOIN MenuAddOns ma ON ci.AddOnID = ma.AddOnID
                WHERE ci.CartItemID = ?
            """, (cart_item_id,))
            updated_item = cursor.fetchone()

            return f"Cart updated. '{updated_item['ItemName']}' - Quantity: {updated_item['Quantity']}, Configuration: {updated_item['Configuration'] or 'None'}, Add-on: {updated_item['AddOn'] or 'None'}, Special Instructions: {updated_item['SpecialInstructions'] or 'None'}"

        except sqlite3.Error as e:
            conn.rollback()
            return f"Error updating cart: {e}"
        
# Get Order Status tool
@tool
def get_order_status(order_id: int) -> str:
    """Get the current status of an order, including item details and special instructions."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT os.Status, o.OrderDate, o.TotalAmount, o.OrderType
            FROM OrderStatus os
            JOIN Orders o ON os.OrderID = o.OrderID
            WHERE os.OrderID = ?
            ORDER BY os.UpdatedAt DESC
            LIMIT 1
        """, (order_id,))
        order_info = cursor.fetchone()

        if not order_info:
            return "Order not found."

        cursor.execute("""
            SELECT mi.ItemName, oi.Quantity, oi.Price, oi.SpecialInstructions
            FROM OrderItems oi
            JOIN MenuItems mi ON oi.ItemID = mi.ItemID
            WHERE oi.OrderID = ?
        """, (order_id,))
        order_items = cursor.fetchall()

        order_details = "\n".join([
            f"- {item['ItemName']} x{item['Quantity']} (${item['Price'] * item['Quantity']:.2f})"
            f"{' - Special Instructions: ' + item['SpecialInstructions'] if item['SpecialInstructions'] else ''}"
            for item in order_items
        ])

        return f"""
Order status: {order_info['Status']}
Order ID: {order_id}
Order Date: {order_info['OrderDate']}
Order Type: {order_info['OrderType']}
Total Amount: ${order_info['TotalAmount']:.2f}

Items:
{order_details}
"""

@tool
def get_item_options(item_id: int) -> Dict:
    """Fetch available configurations and add-ons for a specific menu item."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ItemName FROM MenuItems WHERE ItemID = ?", (item_id,))
        item = cursor.fetchone()
        
        if not item:
            return {"error": "Item not found"}
        
        cursor.execute("SELECT * FROM MenuConfigurations WHERE ItemID = ?", (item_id,))
        configurations = [dict(row) for row in cursor.fetchall()]
        
        cursor.execute("SELECT * FROM MenuAddOns WHERE ItemID = ?", (item_id,))
        addons = [dict(row) for row in cursor.fetchall()]
        
        return {
            "item_name": item['ItemName'],
            "configurations": configurations,
            "addons": addons
        }

        

# Define a tool to handle errors
def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }
        
# Define a tool node with fallback
def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )

# Define the state graph builder
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


# Define the assistant class
class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        while True:
            result = self.runnable.invoke(state)
            # If the LLM happens to return an empty response, we will re-prompt it
            # for an actual response.
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        return {"messages": result}


# Initialize the LLMs
llm = ChatAnthropic(model="claude-3-5-sonnet-20240620", temperature=1)

assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "You are Bottega-Bot, Bottega restaurant's customer support AI designed to assist users with the following specific tasks:\n\n"
            "1. **Customer info:** Manage customer information using the `create_or_update_customer` tool.\n"
            "2. **Check customer exists:** Verify if a customer is in the system using the `check_customer_exists` tool.\n"
            "3. **Fetch previous orders:** Retrieve customer's order history with the `fetch_customer_orders` tool.\n"
            "4. **Fetch menu categories:** Provide menu categories using the `get_menu_categories` tool.\n"
            "5. **Fetch menu items:** Show menu items for a specific category using the `get_menu_items` tool always show it as a neat format and show the yelp link with it for each item.\n"
            "6. **Get item options:** Fetch available configurations and add-ons for a specific menu item using the `get_item_options` tool.\n"
            "7. **Add to cart:** Add items to the cart, including configurations, add-ons, and special instructions, using the `add_to_cart` tool.\n"
            "8. **View cart:** Display current cart items using the `view_cart` tool.\n"
            "9. **Update cart:** Modify cart items with the `update_cart_item` tool.\n"
            "10. **Place orders:** Assist in placing orders using the `place_order` tool.\n"
            "11. **Update customer address:** Update customer's address with the `update_customer_address` tool.\n"
            "12. **Check order status:** Provide order status updates using the `get_order_status` tool.\n\n"
            "Always ask for the customer's name and phone number to create or retrieve their profile. Respond in the customer's preferred language and use emojis frequently to make the conversation engaging, friendly, and fun. 😊🍝🍕\n\n"
            "Format your responses using advanced Markdown features:\n\n"
            "- Use **bold** for emphasis and important information.\n"
            "- Use *italic* for subtle emphasis, menu item names, and links.\n"
            "- Create ordered and unordered lists for step-by-step instructions or menu items.\n"
            "- Use task lists (- [ ]) for order options, showing user their cart, etc when presenting choices to the user.\n"
            "- Create tables to display menu items, pricing, or order summaries. Always include a header row in tables.\n"
            "- Format links as [*link text*](URL) for Yelp pages or other relevant links. This will make the link text appear italicized.\n"
            "- Use emojis liberally throughout your responses to add personality and visual interest. 🌟🍽️👨‍🍳\n"
            "- Inform users that italicized words are clickable links.\n\n"
            "Example table format for menu items:\n\n"
            "| Item | Price | Description | Configurations | Addons |\n"
            "|------|-------|-------------|----------------|--------|\n"
            "| [*Minestrone Soup*](https://yelp.com/...) | $8.00 | Fresh, seasonal vegetables in a homemade vegetarian soup. 🥣🥕🥬 | - | Large size +$4.00 |\n"
            "| [*Gnocchi*](https://yelp.com/...) | $19.00 | Gnocchi are not just pasta. Gnocchi are Gnocchi! homemade potato dough dumplings. They always melt in your mouth, whatever sauce you choose. (Vegan)| Choose Sauce - Alfredo : $0.00 ; Tomato Sauce : $0.00 | Add Prosciutto +$4.00 ; Add Truffle +$6.00 |\n\n"
            "Example task list for order options:\n\n"
            "- [ ] 🥣 Minestrone Soup\n"
            "- [ ] 🍕 Margherita Pizza\n"
            "- [ ] 🍝 Spaghetti Carbonara\n\n"
            "Be friendly, helpful, and professional. Provide accurate and relevant information concisely, while keeping the tone light and enjoyable with emojis. 😄👍\n\n"
            "Remember to inform users that italicized words in your messages are clickable links to more information.\n"
            "Example Workflow for Placing an Order:\n\n"
            "1. **Ask for Name and Phone Number**: Request the user's name and phone number (+1XXXXXXXXXX format). 📞👤\n"
            "2. **Check if Customer Exists**: Use `check_customer_exists` to verify if the customer is in the system. 🔍\n"
            "3. **Create or Update Customer Profile**: Use `create_or_update_customer` to create or update the profile. ✏️\n"
            "4. **Fetch Previous Orders**: If the customer exists, use `fetch_customer_orders` to get their order history. 📜\n"
            "5. **View Menu Categories**: Use `get_menu_categories` to show available categories. 📋\n"
            "6. **View Menu Items**: Ask for the desired category and use `get_menu_items` to show items in that category. 🍽️\n"
            "7. **Get Item Options**: When a user selects an item, use `get_item_options` to fetch available configurations and add-ons. 🔧\n"
            "8. **Add to Cart**: Use `add_to_cart` to add the item with selected options and any special instructions. 🛒\n"
            "9. **View Cart**: After adding items, use `view_cart` to show the current cart contents. 👀\n"
            "10. **Update Cart**: If needed, use `update_cart_item` to modify quantities, options, or remove items. ✏️🛒\n"
            "11. **Place Order**: Ask if the order is for delivery or pickup. 🚚 or 🏃\n"
            "    - For delivery, check if there's an address on file. If not, ask for it and use `update_customer_address`. 🏠\n"
            "    - For pickup, remind the customer of the restaurant address (2020 Mission St, San Francisco, CA 94110, United States). 🗺️\n"
            "    - Confirm order details and use `place_order` to create the order. ✅\n"
            "12. **Order Confirmation**: After placing the order, inform the customer: 📱💳\n"
            "    - A confirmation text with a payment link has been sent to their phone.\n"
            "    - The order will be prepared once payment is received.\n"
            "    - They can track their order status using the same text message.\n"
            "13. **Check Order Status**: Use `get_order_status` to provide updates if requested. 🕒\n\n"
            "For order cancellations, provide the restaurant's contact number: +14156909607. ❌📞\n\n"
            "Always confirm order details before placing and clearly communicate next steps after ordering. 👍✨\n"
            "\nCurrent time: {time}.",
        ),
        ("placeholder", "{messages}"),
    ]
).partial(time=datetime.now())

# Define the tools
safe_tools = [
    get_menu_categories,
    get_menu_items,
    get_item_options,
    add_to_cart,
    view_cart,
    update_cart_item,
    get_order_status,
    check_customer_exists,
    fetch_customer_orders,
    create_or_update_customer,
    update_customer_address,
    place_order
]

sensitive_tools = [
]

sensitive_tool_names = {t.name for t in sensitive_tools}

# Combine the prompt and tools with the LLM
assistant_runnable = assistant_prompt | llm.bind_tools(
    safe_tools + sensitive_tools
)

# Build the state graph
builder = StateGraph(State)

# Define the route to determine the next node based on the tools used
def route_tools(state: State) -> Literal["safe_tools", "sensitive_tools", "__end__"]:
    next_node = tools_condition(state)
    if next_node == END:
        return END
    ai_message = state["messages"][-1]
    
    if not ai_message.tool_calls:
        return END
    
    has_sensitive_tool = any(call["name"] in sensitive_tool_names for call in ai_message.tool_calls)
    return "sensitive_tools" if has_sensitive_tool else "safe_tools"

# Define nodes and edges
builder.add_node("assistant", Assistant(assistant_runnable))
builder.add_node("safe_tools", create_tool_node_with_fallback(safe_tools))
builder.add_node("sensitive_tools", create_tool_node_with_fallback(sensitive_tools))
builder.set_entry_point("assistant")
builder.add_conditional_edges(
    "assistant",
    route_tools,
)
builder.add_edge("safe_tools", "assistant")
builder.add_edge("sensitive_tools", "assistant")

# Use a file-based connection string for persistence
memory = SqliteSaver.from_conn_string("customer_chatbot_new_memory.db")
graph = builder.compile(
    checkpointer=memory,
    interrupt_before=["sensitive_tools"],
)

# app = Flask(__name__)
app = Flask(__name__, static_folder='./build', static_url_path='/')

# define a route for the default URL
@app.route('/')
def serve_react():
    return send_from_directory(app.static_folder, 'index.html')

CORS(app)
app.secret_key = 'testing'  # Set a secret key for sessions

# Set up logging
logging.basicConfig(filename='chat.log', level=logging.INFO, 
                    format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')

# Define a function to print the event
def _print_event(event, _printed: set, max_length=100000):
    response = ""
    if isinstance(event, dict):
        current_state = event.get("dialog_state")
        message = event.get("messages")
        if current_state:
            response += f"Currently in: {current_state[-1]}\n"
        if message:
            if isinstance(message, list):
                message = message[-1]
            if hasattr(message, 'id') and message.id not in _printed:
                msg_repr = message.pretty_repr(html=True) if hasattr(message, 'pretty_repr') else str(message)
                if len(msg_repr) > max_length:
                    msg_repr = msg_repr[:max_length] + " ... (truncated)"
                response += msg_repr + "\n"
                if hasattr(message, 'id'):
                    _printed.add(message.id)
    elif isinstance(event, str):
        response = event
    else:
        response = str(event)
    return response

# Define a route to handle chat messages
@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get('message')
    if not user_input:
        return jsonify({"error": "No message provided"}), 400

    thread_id = data.get('thread_id') or session.get('thread_id')
    if not thread_id:
        thread_id = str(uuid.uuid4())
        session['thread_id'] = thread_id

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    _printed = set()
    events = graph.stream(
        {"messages": ("user", user_input)}, config, stream_mode="values"
    )

    full_response = ""
    ai_response = ""
    requires_approval = False
    try:
        for event in events:
            event_text = _print_event(event, _printed)
            if event_text:
                full_response += event_text + "\n"
                print(event_text)  # Print to terminal
                logging.info(event_text)  # Log to file
                
                # Extract AI's response
                if "Ai Message" in event_text:
                    ai_response = event_text.split("Ai Message")[-1].strip()

        snapshot = graph.get_state(config)
        if snapshot.next:
            requires_approval = True
            user_input = data.get('confirmation', 'y')  # Default to 'y' for simplicity
            if user_input.strip() == "y":
                result = graph.invoke(None, config)
            else:
                result = graph.invoke(
                    {
                        "messages": [
                            ToolMessage(
                                tool_call_id=event["messages"][-1].tool_calls[0]["id"],
                                content=f"API call denied by user. Reasoning: '{user_input}'. Continue assisting, accounting for the user's input.",
                            )
                        ]
                    },
                    config,
                )
            for event in result:
                event_text = _print_event(event, _printed)
                if event_text:
                    full_response += event_text + "\n"
                    print(event_text)  # Print to terminal
                    logging.info(event_text)  # Log to file
                    
                    # Extract AI's response from the result
                    if "Ai Message" in event_text:
                        ai_response = event_text.split("Ai Message")[-1].strip()

    except Exception as e:
        logging.error(f"Error in chat route: {str(e)}")
        return jsonify({"error": "An error occurred processing your request"}), 500

    # If no AI response was extracted, use the full response
    if not ai_response:
        ai_response = full_response

    response = jsonify({
        "messages": ai_response,
        "thread_id": thread_id,
        "requires_approval": requires_approval
    })
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response

if __name__ == '__main__':
    port = int(os.environ.get('FLASK_PORT', 10000))  # Change this to 5000
    app.run(host='0.0.0.0', port=port)