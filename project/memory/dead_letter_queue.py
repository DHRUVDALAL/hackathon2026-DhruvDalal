FAILED_TICKETS = []


def add_failed_ticket(ticket_id, reason):
    """Dead-letter queue for tickets that couldn't be processed even after retries."""
    FAILED_TICKETS.append({
        "ticket_id": str(ticket_id),
        "reason": str(reason),
    })
