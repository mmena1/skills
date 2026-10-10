# Corner shop checkout

Computes delivery charges for online orders.

- Free delivery: orders whose item subtotal is at least the free-delivery minimum ship free. Marketing changes the minimum several times a year; `shop/pricing/delivery.py` is where it is set.
- Carrier rates come from the carrier rate table. A zone missing from the table is charged the national rate plus the remote-area surcharge, and parcels above 20 kg add the heavy-parcel surcharge. The carrier contract defines these rules.

Python 3.11 standard library only. Run `python -m unittest discover -s tests`.
