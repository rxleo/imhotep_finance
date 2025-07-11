from sqlalchemy import text
from extensions import db
from flask import session, request
from datetime import date, datetime

def recalculate_networth(user_id, given_networth, currency=None):
    '''
    This function recalculates networth for a specific currency or all currencies
    if currency is provided, it only calculates for that currency
    '''
    try:
        if currency:
            #calculate for specific currency only
            total_deposit = db.session.execute(
                text("SELECT COALESCE(SUM(CAST(amount AS FLOAT)), 0) FROM trans WHERE user_id = :user_id AND trans_status = :trans_status AND currency = :currency"),
                {"user_id": user_id, "trans_status": "deposit", "currency": currency}
            ).fetchone()[0]

            total_withdraw = db.session.execute(
                text("SELECT COALESCE(SUM(CAST(amount AS FLOAT)), 0) FROM trans WHERE user_id = :user_id AND trans_status = :trans_status AND currency = :currency"),
                {"user_id": user_id, "trans_status": "withdraw", "currency": currency}
            ).fetchone()[0]
        else:
            #calculate for all currencies
            total_deposit = db.session.execute(
                text("SELECT COALESCE(SUM(CAST(amount AS FLOAT)), 0) FROM trans WHERE user_id = :user_id AND trans_status = :trans_status"),
                {"user_id": user_id, "trans_status": "deposit"}
            ).fetchone()[0]

            total_withdraw = db.session.execute(
                text("SELECT COALESCE(SUM(CAST(amount AS FLOAT)), 0) FROM trans WHERE user_id = :user_id AND trans_status = :trans_status"),
                {"user_id": user_id, "trans_status": "withdraw"}
            ).fetchone()[0]

        total_expected = (total_deposit or 0) - (total_withdraw or 0)
        return total_expected

    except Exception as e:
        #if there is anything that goes wrong so we return the given one
        print(f"Error in recalculate_networth: {e}")
        return given_networth
