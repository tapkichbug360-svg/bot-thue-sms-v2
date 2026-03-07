@dashboard_bp.route('/add_money', methods=['POST'])
def add_money():
    \"\"\"API cộng tiền thủ công - ĐÃ FIX LỖI CỘNG DỒN\"\"\"
    user_id = request.form.get('user_id', type=int)
    amount = request.form.get('amount', type=int)
    reason = request.form.get('reason', 'Cộng tiền thủ công')
    
    if not user_id or not amount or amount < 1000:
        flash('Vui lòng nhập đủ thông tin và số tiền phải >= 1000đ', 'danger')
        return redirect(request.referrer or url_for('dashboard.manual'))
    
    with app.app_context():
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            flash(f'Không tìm thấy user có ID {user_id}', 'danger')
            return redirect(request.referrer or url_for('dashboard.manual'))
        
        old_balance = user.balance
        user.balance += amount  # QUAN TRỌNG: CỘNG DỒN
        
        transaction_code = f"MANUAL_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            type='deposit',
            status='success',
            transaction_code=transaction_code,
            description=reason,
            created_at=datetime.now()
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        logger.info(f"✅ ĐÃ CỘNG {amount}đ THỦ CÔNG CHO USER {user_id}")
        logger.info(f"   Số dư: {old_balance}đ → {user.balance}đ (+{amount}đ)")
        
        flash(f'✅ ĐÃ CỘNG {amount:,}đ THÀNH CÔNG!\n'
              f'👤 User: {user_id}\n'
              f'💰 Số dư cũ: {old_balance:,}đ\n'
              f'💰 Số dư mới: {user.balance:,}đ\n'
              f'📝 Mã GD: {transaction_code}', 'success')
    
    return redirect(request.referrer or url_for('dashboard.manual'))
