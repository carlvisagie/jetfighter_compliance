from typing import List, Tuple

def extract_generic(payment_event: dict) -> Tuple[str,str,str,List[str]]:
    return (
        str(payment_event["order_id"]),
        payment_event["email"],
        payment_event.get("name",""),
        list(payment_event.get("skus",[]))
    )
