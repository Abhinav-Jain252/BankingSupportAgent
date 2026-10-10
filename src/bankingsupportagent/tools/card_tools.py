from contextlib import closing
from langchain.tools import tool,ToolRuntime
from bankingsupportagent.tools.account_tools import get_connection, NOT_VERIFIED

# Which status changes are allowed: action -> (required current status, new status)
TRANSITIONS = {
    "freeze": ("active","frozen"),
    "unfreeze": ("frozen","active"),
}


# Helpers
def is_valid_last4(last4:str) -> bool:
    return len(last4) == 4 and last4.isdigit()


# Data functions

def fetch_cards(customer_id: str) -> str:
    with closing(get_connection()) as conn:
        rows = conn.execute(
            "Select card_type, last4, status, international FROM cards where customer_id=?",(customer_id,),
        ).fetchall()

    if not rows:
        return "No card found for this customer"
    return "\n".join(
        f"{r['card_type']} ending {r['last4']} | status: {r['status']} | "
        f"international usage: {'on' if r['international'] else 'off'}"
        for r in rows
    )


def fetch_card_status(customer_id: str, last4: str):
    """Return the card's status and None if this customer has no such card"""
    with closing(get_connection()) as conn:
        row = conn.execute(
            "Select status FROM cards WHERE customer_id=? AND last4=?",(customer_id,last4)
        ).fetchone()

    return row['status'] if row else None


def change_card_status(customer_id:str, last4:str, action:str)->str:
    if not is_valid_last4(last4):
        return "Please give only the last 4 digits of your card. Never share the full card number"

    current = fetch_card_status(customer_id,last4)
    if current is None:
        return f"No card ending {last4} was found on this customer's profile"

    from_status,to_status = TRANSITIONS[action]
    if current!=from_status:
        return f"Cannot {action} the card ending {last4}: it's current status is {current}"

    with closing(get_connection()) as conn:
        conn.execute(
            "UPDATE cards SET status=? WHERE customer_id=? AND last4=?",(to_status,customer_id,last4),
        )
        conn.commit()
    return f"Done. The card ending {last4} is now {to_status}."



# Tools

@tool
def list_cards(runtime:ToolRuntime) -> str:
    """List the logged in customer's card with their last 4 digits and status"""
    customer_id = runtime.state.get("customer_id")
    if not customer_id:
        return NOT_VERIFIED
    return fetch_cards(customer_id)


@tool
def freeze_card(runtime:ToolRuntime, last4:str) -> str:
    """Temporarily freeze one of the customer's cards. A frozen card can be unfrozen later.
    
    Args:
        last4: The last 4 digits of the card to be freeze
    """

    customer_id = runtime.state.get("customer_id")
    if not customer_id:
        return NOT_VERIFIED
    return change_card_status(customer_id,last4,"freeze")


@tool
def unfreeze_card(runtime:ToolRuntime, last4:str) -> str:
    """Unfreeze a card that the customer froze earlier
    
    Args:
        last4: The last 4 digits of the card to unfreeze
    """

    customer_id = runtime.state.get("customer_id")
    if not customer_id:
        return NOT_VERIFIED
    return change_card_status(customer_id,last4,"unfreeze")