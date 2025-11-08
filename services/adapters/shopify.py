from typing import List, Tuple

def extract_paid_order(payload: dict) -> Tuple[str,str,str,List[str]]:
    order_id = str(payload.get("id") or payload.get("order_id"))
    email = payload.get("email") or payload.get("customer",{}).get("email","")
    customer = payload.get("customer",{})
    name = " ".join(filter(None,[customer.get("first_name"), customer.get("last_name")])) or (customer.get("name","") or "")
    lines = payload.get("line_items", [])
    skus = []
    for li in lines:
        sku = (li.get("sku") or "").strip()
        if not sku:
            title = li.get("title","")
            sku = title.upper().replace(" ","-")
        skus.append(sku)
    return (order_id, email, name, skus)
