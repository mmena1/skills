# Rental desk fees

Fee calculations for an equipment rental shop that also takes workshop bookings.

- Late returns follow the rental agreement owned by the rentals team: 10% of the rental price for each started day late, capped at the full rental price, rounded half up to the cent.
- Workshop cancellations follow the consumer booking terms owned by the legal team: 15% of the booking price with a minimum of 5.00, never more than the amount actually paid, rounded down to the cent.

The two policies have different owners and change on different schedules; a change to one must not alter the other.

Python 3.11 standard library only. Run `python -m unittest discover -s tests`.
