from flask import render_template, redirect, session, request, Blueprint, flash, flash, url_for, Response
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from extensions import db
from config import CSRFForm, Config
from utils.user_info import select_user_photo, trans, get_app_currencies, get_user_categories
from utils.currencies import show_networth, select_currencies
from datetime import datetime
from openpyxl import Workbook
import io
import csv
from utils.recalculate_networth import recalculate_networth

transactions_bp = Blueprint('transactions', __name__)

@transactions_bp.route("/deposit", methods=["POST", "GET"])
def deposit():
    if not session.get("logged_in"):
        return redirect("/login_page")
    else:
        try:
            user_photo_path = select_user_photo()
        except OperationalError:
            error = "Welcome Back"
            return render_template('error.html', error=error, form=CSRFForm())
        
        user_id = session.get("user_id")
        total_favorite_currency, favorite_currency = show_networth()
        total_favorite_currency = f"{total_favorite_currency:,.2f}"

        # Get user's most frequent income categories
        user_categories = get_user_categories("deposit", user_id)

        if request.method == "GET":
            return render_template("deposit.html",
                                    user_photo_path=user_photo_path,
                                    total_favorite_currency=total_favorite_currency,
                                    favorite_currency=favorite_currency,
                                    form=CSRFForm(),
                                    available_currencies=get_app_currencies(),
                                    user_categories=user_categories)
        else:

            date = request.form.get("date")
            amount = float(request.form.get("amount"))
            currency = request.form.get("currency")
            user_id = session.get("user_id")
            trans_details = request.form.get("trans_details")
            category = request.form.get("category")

            if currency is None or amount is None :
                error = "You have to choose the currency!"
                return render_template("deposit.html", error = error,total_favorite_currency=total_favorite_currency, favorite_currency=favorite_currency,  user_photo_path=user_photo_path, form=CSRFForm())

            try:
                last_trans_id = db.session.execute(
                        text("SELECT MAX(trans_id) FROM trans WHERE user_id = :user_id"),
                        {"user_id": user_id}
                    ).fetchone()[0]
                trans_id = last_trans_id + 1
            except:
                trans_id = 1

            try:
                last_trans_key = db.session.execute(
                    text("SELECT MAX(trans_key) FROM trans")
                ).fetchone()[0]
                trans_key = last_trans_key + 1
            except:
                trans_key = 1

            db.session.execute(
                text("INSERT INTO trans (date, trans_key, amount, currency, user_id, trans_id, trans_status, trans_details, category) VALUES (:date, :trans_key, :amount, :currency, :user_id, :trans_id, :trans_status, :trans_details, :category)"),
                  {"date": date,"trans_key":trans_key, "amount": amount, "currency": currency, "user_id": user_id, "trans_id": trans_id, "trans_status": "deposit", "trans_details": trans_details, "category":category}
            )
            db.session.commit()

            networth_db = db.session.execute(
                text("SELECT networth_id, total FROM networth WHERE user_id = :user_id AND currency = :currency"),
                {"user_id": user_id, "currency": currency}
            ).fetchone()

            if networth_db:
                networth_id = networth_db[0]
                total = float(networth_db[1])

                new_total_calc = total + amount

                #to make sure that the networth is calculated correctly and there is no unexpected error happened
                new_total = recalculate_networth(user_id, new_total_calc, currency)

                db.session.execute(
                    text("UPDATE networth SET total = :total WHERE networth_id = :networth_id"),
                    {"total" :new_total, "networth_id": networth_id}
                )
                db.session.commit()

            else:
                networth_id = db.session.execute(
                    text("SELECT COALESCE(MAX(networth_id), 0) + 1 FROM networth")
                ).fetchone()[0]
                
                db.session.execute(
                    text("INSERT INTO networth (networth_id,  user_id , currency, total) VALUES (:networth_id,  :user_id , :currency, :total)"),
                    {"networth_id": networth_id, "user_id": user_id, "currency": currency, "total": amount}
                )
                db.session.commit()

            return redirect("/home")

@transactions_bp.route("/withdraw", methods=["POST", "GET"])
def withdraw():
    if not session.get("logged_in"):
        return redirect("/login_page")
    else:
        try:
            user_photo_path = select_user_photo()
        except OperationalError:
            error = "Welcome Back"
            return render_template('error.html', error=error, form=CSRFForm())
        total_favorite_currency, favorite_currency = show_networth()
        total_favorite_currency = f"{total_favorite_currency:,.2f}"
        
        user_id = session.get("user_id")
        user_categories = get_user_categories("withdraw", user_id)
        
        if request.method == "GET":
            currency_all = select_currencies(user_id)
            return render_template("withdraw.html", 
                                 currency_all=currency_all, 
                                 user_photo_path=user_photo_path, 
                                 total_favorite_currency=total_favorite_currency, 
                                 favorite_currency=favorite_currency, 
                                 form=CSRFForm(),
                                 user_categories=user_categories)

        else:
            date = request.form.get("date")
            amount = float(request.form.get("amount"))
            currency = request.form.get("currency")
            trans_details = request.form.get("trans_details")
            trans_details_link = request.form.get("trans_details_link")
            category = request.form.get("category")

            if currency == None or date == None or amount == None :
                error = "You have to choose the currency!"
                currency_all = select_currencies(user_id)
                return render_template("withdraw.html", 
                                     currency_all=currency_all, 
                                     error=error, 
                                     user_photo_path=user_photo_path, 
                                     total_favorite_currency=total_favorite_currency, 
                                     favorite_currency=favorite_currency, 
                                     form=CSRFForm(),
                                     user_categories=user_categories)
            
            amount_of_currency = db.session.execute(
                text("SELECT total FROM networth WHERE user_id = :user_id AND currency = :currency"),
                {"user_id": user_id, "currency":currency}
            ).fetchone()[0]

            if amount > amount_of_currency:
                error = "This user doesn't have this amount of this currency"
                currency_all = select_currencies(user_id)
                return render_template("withdraw.html", 
                                     currency_all=currency_all, 
                                     error=error, 
                                     user_photo_path=user_photo_path, 
                                     total_favorite_currency=total_favorite_currency, 
                                     favorite_currency=favorite_currency, 
                                     form=CSRFForm(),
                                     user_categories=user_categories)
            
            try:
                last_trans_id = db.session.execute(
                        text("SELECT MAX(trans_id) FROM trans WHERE user_id = :user_id"),
                        {"user_id": user_id}
                    ).fetchone()[0]
                trans_id = last_trans_id + 1
            except:
                trans_id = 1

            last_trans_key = db.session.execute(
                text("SELECT MAX(trans_key) FROM trans")
            ).fetchone()[0]
            if last_trans_key:
                trans_key = last_trans_key + 1
            else:
                trans_key = 1

            db.session.execute(
                text("INSERT INTO trans (date, trans_key, amount, currency, user_id, trans_id, trans_status, trans_details, trans_details_link, category) VALUES (:date, :trans_key, :amount, :currency, :user_id, :trans_id, :trans_status, :trans_details, :trans_details_link, :category)"),
                  {"date": date,"trans_key":trans_key, "amount": amount, "currency": currency, "user_id": user_id, "trans_id": trans_id, "trans_status": "withdraw", "trans_details": trans_details, "trans_details_link": trans_details_link, "category":category}
            )
            db.session.commit()

            try:
                networth_db = db.session.execute(
                    text("SELECT networth_id, total FROM networth WHERE user_id = :user_id AND currency = :currency"),
                    {"user_id": user_id, "currency": currency}
                ).fetchone()
                networth_id = networth_db[0]
                total = float(networth_db[1])

                new_total_calc = total - amount
                
                #to make sure that the networth is calculated correctly and there is no unexpected error happened
                new_total = recalculate_networth(user_id, new_total_calc, currency)

                db.session.execute(
                    text("UPDATE networth SET total = :total WHERE networth_id = :networth_id"),
                    {"total" :new_total, "networth_id": networth_id}
                )
                db.session.commit()

            except:
                error = "You don't have money from that currency!"
            return redirect("/home")

@transactions_bp.route("/show_trans", methods=["GET"])
def show_trans():
    if not session.get("logged_in"):
        return redirect("/login_page")
    else:
        user_id = session.get("user_id")
        try:
            user_photo_path = select_user_photo()
        except OperationalError:
            error = "Welcome Back"
            return render_template('error.html', error=error, form=CSRFForm())

        total_favorite_currency, favorite_currency = show_networth()
        total_favorite_currency = f"{total_favorite_currency:,.2f}"

        trans_db, to_date,from_date, total_pages, page = trans(user_id)    

        return render_template("show_trans.html", trans_db=trans_db, user_photo_path=user_photo_path, total_favorite_currency=total_favorite_currency, favorite_currency=favorite_currency, to_date=to_date, from_date=from_date, total_pages=total_pages,page=page, form=CSRFForm())

@transactions_bp.route("/edit_trans", methods=["POST", "GET"])
def edit_trans():
    if not session.get("logged_in"):
        return redirect("/login_page")
    else:
        try:
            user_photo_path = select_user_photo()
        except OperationalError:
            error = "Welcome Back"
            return render_template('error.html', error=error, form=CSRFForm())

        user_id = session.get("user_id")
        if request.method == "GET":
            trans_key = request.args.get("trans_key")
            trans_db = db.session.execute(
                text("SELECT * FROM trans WHERE trans_key = :trans_key"),
                {"trans_key" :trans_key}
            ).fetchall()[0]
            total_favorite_currency, favorite_currency = show_networth()
            total_favorite_currency = f"{total_favorite_currency:,.2f}"
            return render_template("edit_trans.html",
                                    trans_db = trans_db,
                                    user_photo_path=user_photo_path,
                                    total_favorite_currency=total_favorite_currency,
                                    favorite_currency=favorite_currency,
                                    form=CSRFForm(),
                                    currency = trans_db[3])

        else:

            trans_key = request.form.get("trans_key")
            currency = request.form.get("currency")
            date = request.form.get("date")
            amount = request.form.get("amount")
            trans_details = request.form.get("trans_details")
            trans_details_link = request.form.get("trans_details_link")
            category = request.form.get("category")
            
            print(trans_key)
            amount_currency_db = db.session.execute(
                text("SELECT amount, currency, trans_status FROM trans WHERE trans_key = :trans_key"),
                {"trans_key" :trans_key}
            ).fetchone()

            amount_db = float(amount_currency_db[0])
            status_db = amount_currency_db[2]

            if currency in select_currencies(user_id):
                total_db = db.session.execute(
                    text("SELECT total from networth WHERE user_id = :user_id and currency = :currency"),
                    {"user_id" :user_id, "currency" :currency}
                ).fetchone()[0]
            else:
                total_db = 0

            total_db = float(total_db)

            if status_db == "withdraw":
                total_db += amount_db
                total = total_db - float(amount)

            elif status_db == "deposit":
                total_db -= amount_db
                total = total_db + float(amount)
            
            if total < 0:
                error = "you don't have enough money from this currency!"
                trans_db = db.session.execute(
                    text("SELECT * FROM trans WHERE trans_key = :trans_key"),
                    {"trans_key" :trans_key}
                ).fetchall()[0]
                total_favorite_currency, favorite_currency = show_networth()
                total_favorite_currency = f"{total_favorite_currency:,.2f}"
                return render_template("edit_trans.html", 
                                     trans_db = trans_db, 
                                     user_photo_path=user_photo_path, 
                                     error=error, 
                                     total_favorite_currency=total_favorite_currency, 
                                     favorite_currency=favorite_currency, 
                                     form=CSRFForm(),
                                     available_currencies = get_app_currencies())

            db.session.execute(
                text("UPDATE trans SET  date = :date, trans_details = :trans_details, trans_details_link = :trans_details_link, amount = :amount, category = :category WHERE trans_key = :trans_key"),
                {"date" :date, "trans_details" :trans_details, "trans_details_link" :trans_details_link, "amount" :amount, "trans_key" :trans_key, "category":category}
            )
            db.session.commit()

            #to make sure that the networth is calculated correctly and there is no unexpected error happened
            new_total = recalculate_networth(user_id, total, currency)

            db.session.execute(
                text("UPDATE networth SET total = :total WHERE user_id = :user_id and currency = :currency"),
                {"total" :new_total, "user_id" :user_id, "currency" :currency}
            )
            db.session.commit()

            trans_db, to_date,from_date, total_pages, page = trans(user_id) 

            total_favorite_currency, favorite_currency = show_networth()
            total_favorite_currency = f"{total_favorite_currency:,.2f}"
            return render_template("show_trans.html", trans_db=trans_db, user_photo_path=user_photo_path, total_favorite_currency=total_favorite_currency, favorite_currency=favorite_currency, to_date =to_date ,from_date=from_date, total_pages=total_pages, page=page, form=CSRFForm())

@transactions_bp.route("/delete_trans", methods=["POST"])
def delete_trans():
    if not session.get("logged_in"):
        return redirect("/login_page")
    else:

        try:
            user_photo_path = select_user_photo()
        except OperationalError:
            error = "Welcome Back"
            return render_template('error.html', error=error, form=CSRFForm())

        total_favorite_currency, favorite_currency = show_networth()
        total_favorite_currency = f"{total_favorite_currency:,.2f}"
        user_id = session.get("user_id")
        trans_key = request.form.get("trans_key")
        trans_db = db.session.execute(
            text("SELECT amount, currency, trans_status FROM trans WHERE trans_key = :trans_key"),
            {"trans_key" :trans_key}
        ).fetchone()

        amount_db = trans_db[0]
        currency_db = trans_db[1]
        trans_status_db = trans_db[2]

        total_db = db.session.execute(
            text("SELECT total FROM networth WHERE user_id = :user_id and currency = :currency"),
            {"user_id" :user_id, "currency" :currency_db}
        ).fetchone()[0]

        if trans_status_db == "deposit":
            total = total_db - float(amount_db)
            if total < 0:
                error = "You can't delete this transaction"
                trans_db = db.session.execute(
                    text("SELECT * FROM trans WHERE user_id = :user_id"),
                    {"user_id": user_id}
                ).fetchall()
                trans_db, to_date,from_date, total_pages, page = trans(user_id) 

                return render_template("show_trans.html", trans_db=trans_db, user_photo_path=user_photo_path, total_favorite_currency=total_favorite_currency, favorite_currency=favorite_currency, page = page,total_pages=total_pages,to_date=to_date, from_date=from_date,error=error, form=CSRFForm())

        elif trans_status_db == "withdraw":
            total = total_db + float(amount_db)

        trans_data_db = db.session.execute(
                text("SELECT currency, date, amount, trans_status, trans_details, trans_details_link, category FROM trans WHERE user_id = :user_id AND trans_key = :trans_key"),
                {"user_id": user_id, "trans_key" :trans_key}
            ).fetchone()
        
        currency = trans_data_db[0]
        date = trans_data_db[1]
        amount = trans_data_db[2]
        trans_status = trans_data_db[3]
        trans_details = trans_data_db[4]
        trans_details_link = trans_data_db[5]
        category = trans_data_db[6]

        try:
            last_trans_trash_id = db.session.execute(
                    text("SELECT MAX(trans_trash_id) FROM trans_trash WHERE user_id = :user_id"),
                    {"user_id": user_id}
                ).fetchone()[0]
            trans_trash_id = last_trans_trash_id + 1
        except:
            trans_trash_id = 1

        try:
            last_trans_trash_key = db.session.execute(
                text("SELECT MAX(trans_trash_key) FROM trans_trash")
            ).fetchone()[0]
            trans_trash_key = last_trans_trash_key + 1
        except:
            trans_trash_key = 1

        db.session.execute(
            text("INSERT INTO trans_trash (trans_trash_key, trans_trash_id, user_id, currency, date, amount, trans_status, trans_details, trans_details_link, category) VALUES(:trans_trash_key, :trans_trash_id, :user_id, :currency, :date, :amount, :trans_status, :trans_details, :trans_details_link, :category)"),
            {"trans_trash_key" :trans_trash_key, "trans_trash_id": trans_trash_id, "user_id": user_id, "currency": currency, "date": date, "amount": amount, "trans_status": trans_status, "trans_details": trans_details, "trans_details_link": trans_details_link, "category":category}
        )
        db.session.commit()

        db.session.execute(
            text("DELETE FROM trans WHERE trans_key = :trans_key"),
            {"trans_key" :trans_key}
        )
        db.session.commit()

        #to make sure that the networth is calculated correctly and there is no unexpected error happened
        total = recalculate_networth(user_id, total, currency)

        db.session.execute(
            text("UPDATE networth SET total = :total WHERE user_id = :user_id AND currency = :currency"),
            {"total" :total, "user_id" :user_id, "currency" :currency_db}
        )
        db.session.commit()

        db.session.execute(
            text("UPDATE wishlist SET status = :status WHERE trans_key = :trans_key"),
            {"status" :"pending", "trans_key" :trans_key}
        )
        db.session.commit()

        trans_db, to_date,from_date, total_pages, page = trans(user_id) 

        return render_template("show_trans.html", trans_db=trans_db, user_photo_path=user_photo_path, total_favorite_currency=total_favorite_currency, favorite_currency=favorite_currency, page = page,total_pages=total_pages,to_date=to_date, from_date=from_date, form=CSRFForm())


@transactions_bp.route("/trash_trans", methods=["GET", "POST"])
def trash_trans():
    if not session.get("logged_in"):
        return redirect("/login_page")
    else:
        try:
            user_photo_path = select_user_photo()
        except OperationalError:
            error = "Welcome Back"
            return render_template('error.html', error=error, form=CSRFForm())

        total_favorite_currency, favorite_currency = show_networth()
        total_favorite_currency = f"{total_favorite_currency:,.2f}"
        user_id = session.get("user_id")
        if request.method == "GET":

            trash_trans_data = db.session.execute(
                text("SELECT * FROM trans_trash WHERE user_id = :user_id"),
                {"user_id" :user_id}
            ).fetchall()

            return render_template("trash_trans.html",user_photo_path=user_photo_path, total_favorite_currency=total_favorite_currency, favorite_currency=favorite_currency, trash_trans_data=trash_trans_data, form=CSRFForm())

        else:

            trans_trash_key = request.form.get("trans_trash_key")
            trash_trans_data = db.session.execute(
                text("SELECT currency, date, amount, trans_status, trans_details, trans_details_link, category FROM trans_trash WHERE user_id = :user_id AND trans_trash_key = :trans_trash_key"),
                {"user_id" :user_id, "trans_trash_key" :trans_trash_key}
            ).fetchone()

            try:
                last_trans_id = db.session.execute(
                        text("SELECT MAX(trans_id) FROM trans WHERE user_id = :user_id"),
                        {"user_id": user_id}
                    ).fetchone()[0]
                trans_id = last_trans_id + 1
            except:
                trans_id = 1

            try:
                last_trans_key = db.session.execute(
                    text("SELECT MAX(trans_key) FROM trans")
                ).fetchone()[0]
                trans_key = last_trans_key + 1
            except:
                trans_key = 1

            currency = trash_trans_data[0]
            date = trash_trans_data[1]
            amount = trash_trans_data[2]
            trans_status = trash_trans_data[3]
            trans_details = trash_trans_data[4]
            trans_details_link = trash_trans_data[5]
            category = trash_trans_data[6]

            db.session.execute(
                text("INSERT INTO trans (trans_key, trans_id, user_id, currency, date, amount, trans_status, trans_details, trans_details_link, category) VALUES (:trans_key, :trans_id, :user_id, :currency, :date, :amount, :trans_status, :trans_details, :trans_details_link, :category)"),
                {"trans_key": trans_key, "trans_id": trans_id, "user_id" :user_id, "currency" :currency, "date" :date, "amount" :amount, "trans_status" :trans_status, "trans_details" :trans_details, "trans_details_link" :trans_details_link, "category":category}
            )
            db.session.commit()

            total_db = db.session.execute(
                text("SELECT total FROM networth WHERE user_id = :user_id and currency = :currency"),
                {"user_id" :user_id, "currency" :currency}
            ).fetchone()[0]

            if trans_status == "deposit":
                total = total_db + float(amount)
            elif trans_status == "withdraw":
                total = total_db - float(amount)

            #to make sure that the networth is calculated correctly and there is no unexpected error happened
            total = recalculate_networth(user_id, total, currency)

            db.session.execute(
                text("UPDATE networth SET total = :total WHERE user_id = :user_id AND currency = :currency"),
                {"total" :total, "user_id" :user_id, "currency" :currency}
            )
            db.session.commit()

            db.session.execute(
                text("DELETE FROM trans_trash WHERE trans_trash_key = :trans_trash_key"),
                {"trans_trash_key" :trans_trash_key}
            )
            db.session.commit()

            trash_trans_data = db.session.execute(
                text("SELECT * FROM trans_trash WHERE user_id = :user_id"),
                {"user_id" :user_id}
            ).fetchall()

            return render_template("trash_trans.html",user_photo_path=user_photo_path, total_favorite_currency=total_favorite_currency, favorite_currency=favorite_currency, trash_trans_data=trash_trans_data, form=CSRFForm())

@transactions_bp.route("/delete_trash_trans", methods=["POST"])
def delete_trash_trans():
    if not session.get("logged_in"):
        return redirect("/login_page")
    else:
        try:
            user_photo_path = select_user_photo()
        except OperationalError:
            error = "Welcome Back"
            return render_template('error.html', error=error, form=CSRFForm())

        total_favorite_currency, favorite_currency = show_networth()
        total_favorite_currency = f"{total_favorite_currency:,.2f}"
        user_id = session.get("user_id")

        trans_trash_key = request.form.get("trans_trash_key")

        db.session.execute(
            text("DELETE FROM trans_trash WHERE trans_trash_key = :trans_trash_key"),
            {"trans_trash_key" :trans_trash_key}
        )
        db.session.commit()

        trash_trans_data = db.session.execute(
            text("SELECT * FROM trans_trash WHERE user_id = :user_id"),
            {"user_id" :user_id}
        ).fetchall()

        return render_template("trash_trans.html",user_photo_path=user_photo_path, total_favorite_currency=total_favorite_currency, favorite_currency=favorite_currency, trash_trans_data=trash_trans_data, form=CSRFForm())

@transactions_bp.route("/export_trans", methods=["GET"])
def export():
    if not session.get("logged_in"):
        return redirect("/login_page")
    else:
        user_id = session.get("user_id")
        try:
            user_photo_path = select_user_photo()
        except OperationalError:
            error = "Welcome Back"
            return render_template('error.html', error=error, form=CSRFForm())

        #get the same filtered transactions as show_trans
        trans_db, to_date, from_date, total_pages, page = trans(user_id)    

        #create CSV data
        output = io.StringIO()
        writer = csv.writer(output)
        
        # CSV Headers
        headers = ['Date', 'Type', 'Amount', 'Currency', 'Category', 'Description', 'Receipt Link', 'Transaction ID']
        writer.writerow(headers)

        # Write transaction data
        for transaction in trans_db:
            writer.writerow([
                transaction[4].strftime('%Y-%m-%d') if transaction[4] else '',  #date
                transaction[6] if transaction[6] else '',  # Type (deposit/withdraw)
                float(transaction[5]) if transaction[5] else 0,  # Amount
                transaction[3] if transaction[3] else '',  # Currency
                transaction[9] if transaction[9] else 'No Category',  # Category
                transaction[7] if transaction[7] else 'No Description',  # Description
                transaction[8] if transaction[8] else '',  # Receipt Link
                transaction[1] if transaction[1] else ''  # Transaction Key
            ])

        # Prepare response
        output.seek(0)
        csv_data = output.getvalue()
        output.close()

        response = Response(
            csv_data,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename=transactions_{from_date}_to_{to_date}.csv'
            }
        )

        return response
