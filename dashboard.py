from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
from database.models import db, User, Transaction, Rental
from datetime import datetime, timedelta
import os
import secrets
import logging
import json
import requests
from collections import defaultdict

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Cấu hình database
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'bot.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# API Configuration
API_KEY = "eyJhbGciOiJIUzUxMiJ9.eyJzdWIiOiJ6emxhbXp6MTEyMiIsImp0aSI6IjgwNTYwIiwiaWF0IjoxNzYxNjEyODAzLCJleHAiOjE4MjM4MjA4MDN9.4u-0IEkd2dgB6QtLEMlgp0KG55JwDDfMiNd98BQNzuJljOA9UTDymPsqnheIqGFM7WVGx94iV71tZasx62JIvw"
BASE_URL = "https://apisim.codesim.net"

# BASE TEMPLATE
BASE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Bot Thuê SMS - Dashboard Quản Lý</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.8.1/font/bootstrap-icons.css">
    <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
    <style>
        body { background: #f8f9fa; font-family: 'Segoe UI', sans-serif; }
        .navbar { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .navbar-brand, .nav-link { color: white !important; }
        .nav-link:hover { background: rgba(255,255,255,0.1); border-radius: 5px; }
        .card { border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 20px; border: none; }
        .card-header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 15px 15px 0 0 !important; }
        .stat-card { background: white; padding: 25px; border-radius: 15px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.1); transition: transform 0.3s; }
        .stat-card:hover { transform: translateY(-5px); }
        .stat-number { font-size: 36px; font-weight: bold; color: #667eea; }
        .profit-number { font-size: 36px; font-weight: bold; color: #28a745; }
        .loss-number { font-size: 36px; font-weight: bold; color: #dc3545; }
        .table thead { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .table thead th { border: none; }
        .search-box { border-radius: 20px; padding: 8px 15px; border: 1px solid #ddd; width: 100%; }
        .modal-content { border-radius: 15px; }
        .flash-message { position: fixed; top: 20px; right: 20px; z-index: 9999; animation: slideIn 0.5s; }
        @keyframes slideIn { from { transform: translateX(100%); } to { transform: translateX(0); } }
        .total-revenue { font-size: 48px; font-weight: bold; color: #28a745; }
        .warning-text { color: #dc3545; font-weight: bold; }
    </style>
</head>
<body>
    <!-- Flash messages -->
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }} alert-dismissible fade show flash-message" role="alert">
                    {{ message | safe }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    <nav class="navbar navbar-expand-lg navbar-dark">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="bi bi-graph-up"></i> Bot Thuê SMS - Quản Lý</a>
            <div class="collapse navbar-collapse">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item"><a class="nav-link" href="/"><i class="bi bi-house-door"></i> Dashboard</a></li>
                    <li class="nav-item"><a class="nav-link" href="/users"><i class="bi bi-people"></i> Người dùng</a></li>
                    <li class="nav-item"><a class="nav-link" href="/transactions"><i class="bi bi-cash-stack"></i> Giao dịch</a></li>
                    <li class="nav-item"><a class="nav-link" href="/profit"><i class="bi bi-graph-up-arrow"></i> Lợi nhuận</a></li>
                    <li class="nav-item"><a class="nav-link" href="/manual"><i class="bi bi-plus-circle"></i> Cộng tiền</a></li>
                    <li class="nav-item"><a class="nav-link" href="/web-deposit"><i class="bi bi-credit-card"></i> Nạp Web</a></li>
                    <li class="nav-item"><a class="nav-link" href="/api-docs"><i class="bi bi-code-slash"></i> API</a></li>
                    <li class="nav-item"><a class="nav-link" href="/statistics"><i class="bi bi-bar-chart"></i> Thống kê</a></li>
                    <li class="nav-item"><span class="nav-link"><i class="bi bi-clock"></i> {{ now.strftime('%H:%M %d/%m/%Y') }}</span></li>
                </ul>
            </div>
        </div>
    </nav>

    <div class="container mt-4">
        {% block content %}{% endblock %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

# INDEX TEMPLATE
INDEX_TEMPLATE = '''
<div class="row">
    <div class="col-md-12">
        <div class="card">
            <div class="card-header"><h5><i class="bi bi-calendar"></i> Thống kê tổng quan</h5></div>
            <div class="card-body">
                <div class="row">
                    <div class="col-md-3"><div class="stat-card"><i class="bi bi-people" style="font-size:40px; color:#667eea;"></i><div class="stat-number">{{ "{:,.0f}".format(stats.total_users) }}</div><div class="stat-label">Tổng người dùng</div></div></div>
                    <div class="col-md-3"><div class="stat-card"><i class="bi bi-person-plus" style="font-size:40px; color:#28a745;"></i><div class="stat-number">{{ "{:,.0f}".format(stats.new_users) }}</div><div class="stat-label">Người dùng mới</div></div></div>
                    <div class="col-md-3"><div class="stat-card"><i class="bi bi-cart" style="font-size:40px; color:#fd7e14;"></i><div class="stat-number">{{ "{:,.0f}".format(stats.total_orders) }}</div><div class="stat-label">Tổng số thuê</div></div></div>
                    <div class="col-md-3"><div class="stat-card"><i class="bi bi-check-circle" style="font-size:40px; color:#28a745;"></i><div class="stat-number">{{ "{:,.0f}".format(stats.success_orders) }}</div><div class="stat-label">Thành công</div></div></div>
                </div>
                <div class="row mt-4">
                    <div class="col-md-4"><div class="card"><div class="card-header"><h5>Doanh thu</h5></div><div class="card-body text-center"><div class="total-revenue">{{ "{:,.0f}".format(stats.revenue) }}đ</div><p class="text-muted">Tổng doanh thu</p><div class="row"><div class="col-6"><h6><i class="bi bi-arrow-up-circle text-success"></i> Nạp tiền</h6><h4 class="text-success">{{ "{:,.0f}".format(stats.deposit) }}đ</h4></div><div class="col-6"><h6><i class="bi bi-arrow-down-circle text-primary"></i> Thuê số</h6><h4 class="text-primary">{{ "{:,.0f}".format(stats.rental) }}đ</h4></div></div></div></div></div>
                    <div class="col-md-4"><div class="card"><div class="card-header"><h5>Chi phí</h5></div><div class="card-body text-center"><div class="total-revenue" style="color:#dc3545;">{{ "{:,.0f}".format(stats.cost) }}đ</div><p class="text-muted">Tổng chi phí</p><div class="row"><div class="col-6"><h6><i class="bi bi-tag"></i> Giá vốn</h6><h4>{{ "{:,.0f}".format(stats.cost) }}đ</h4></div><div class="col-6"><h6><i class="bi bi-percent"></i> Biên LN</h6><h4 class="{% if stats.profit_margin >= 0 %}text-success{% else %}text-danger{% endif %}">{{ "{:.1f}".format(stats.profit_margin) }}%</h4></div></div></div></div></div>
                    <div class="col-md-4"><div class="card"><div class="card-header"><h5>Lợi nhuận</h5></div><div class="card-body text-center"><div class="{% if stats.profit >= 0 %}profit-number{% else %}loss-number{% endif %}">{{ "{:,.0f}".format(stats.profit) }}đ</div><p class="text-muted">Lợi nhuận ròng</p><div class="row"><div class="col-6"><h6><i class="bi bi-arrow-up-circle text-success"></i> Phí DV</h6><h4 class="text-success">{{ "{:,.0f}".format(stats.service_fee) }}đ</h4></div><div class="col-6"><h6><i class="bi bi-clock"></i> Giao dịch</h6><h4>{{ stats.total_orders }}</h4></div></div></div></div></div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- Giao dịch gần đây -->
<div class="card mt-4">
    <div class="card-header"><h5><i class="bi bi-clock-history"></i> Giao dịch gần đây</h5></div>
    <div class="card-body">
        <table class="table table-striped">
            <thead><tr><th>Thời gian</th><th>User</th><th>Loại</th><th>Dịch vụ</th><th>Số tiền</th><th>Lợi nhuận</th><th>Trạng thái</th></tr></thead>
            <tbody>
                {% for trans in stats.recent_transactions %}
                <tr>
                    <td>{{ trans.time }}</td><td><code>{{ trans.user_id }}</code></td>
                    <td><span class="badge bg-{{ 'success' if trans.type == 'Nạp tiền' else 'primary' }}">{{ trans.type }}</span></td>
                    <td>{{ trans.service or '-' }}</td>
                    <td>{{ "{:,.0f}".format(trans.amount) }}đ</td>
                    <td class="text-success">{{ "{:,.0f}".format(trans.profit) }}đ</td>
                    <td><span class="badge bg-success">Thành công</span></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
'''

# WEB DEPOSIT TEMPLATE
WEB_DEPOSIT_TEMPLATE = '''
<div class="row">
    <div class="col-md-8 mx-auto">
        <div class="card">
            <div class="card-header bg-warning text-dark">
                <h5><i class="bi bi-exclamation-triangle-fill"></i> TUÂN THỦ PHÁP LUẬT</h5>
            </div>
            <div class="card-body">
                <div class="alert alert-danger">
                    <strong>⚠️ NGHIÊM CẤM:</strong><br>
                    - Sử dụng số cho mục đích đánh bạc online, cá độ, tài xỉu, lừa đảo<br>
                    - Tạo BANK ẢO, tiền ảo<br>
                    - Lọc các loại nick Facebook cũ, TikTok cũ, Zalo cũ<br>
                    - Chọn SAI dịch vụ<br><br>
                    <strong>Mọi thông tin chuyển khoản và sử dụng số đều được lưu lại để tuân thủ pháp luật.</strong><br>
                    <strong class="text-danger">Dịch vụ ZALO, Telegram hiện tại đang CẤM!</strong><br>
                    <strong>Vi phạm sẽ khóa acc vĩnh viễn, không hoàn lại tiền.</strong>
                </div>
            </div>
        </div>

        <div class="card mt-3">
            <div class="card-header">
                <h5><i class="bi bi-credit-card"></i> Nạp tiền qua Web</h5>
            </div>
            <div class="card-body">
                <form method="POST" action="/web-deposit">
                    <div class="mb-3">
                        <label class="form-label">User ID (Telegram ID)</label>
                        <input type="number" class="form-control" name="user_id" required placeholder="5180190297">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Số tiền (VNĐ)</label>
                        <input type="number" class="form-control" name="amount" min="10000" step="10000" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Phương thức</label>
                        <select class="form-control" name="method">
                            <option value="momo">Momo</option>
                            <option value="bank">Chuyển khoản ngân hàng</option>
                            <option value="card">Thẻ cào</option>
                        </select>
                    </div>
                    <button type="submit" class="btn btn-warning w-100"><i class="bi bi-cash"></i> Tạo yêu cầu nạp tiền</button>
                </form>
            </div>
        </div>
    </div>
</div>
'''

# API DOCS TEMPLATE
API_DOCS_TEMPLATE = '''
<div class="row">
    <div class="col-md-12">
        <div class="card">
            <div class="card-header">
                <h5><i class="bi bi-code-slash"></i> Tích hợp API</h5>
            </div>
            <div class="card-body">
                <div class="alert alert-info">
                    <strong>API Key của bạn:</strong> <code>{{ api_key }}</code><br>
                    <strong>Username:</strong> zzlamzz1122<br>
                    <strong>Số dư:</strong> {{ balance }}đ
                </div>

                <h5 class="mt-4">1. Lấy thông tin tài khoản</h5>
                <div class="bg-light p-3 rounded">
                    <strong>GET</strong> <code>{{ base_url }}/yourself/information-by-api-key?api_key={{ api_key }}</code>
                </div>
                <pre class="bg-dark text-light p-3 mt-2 rounded">
{
  "status": 200,
  "data": {
    "balance": 46100,
    "username": "abababab"
  }
}</pre>

                <h5 class="mt-4">2. Lấy danh sách dịch vụ</h5>
                <div class="bg-light p-3 rounded">
                    <strong>GET</strong> <code>{{ base_url }}/service/get_service_by_api_key?api_key={{ api_key }}</code>
                </div>
                <pre class="bg-dark text-light p-3 mt-2 rounded">
{
  "status": 200,
  "data": [
    {"id": 1, "name": "Facebook", "price": 1200},
    {"id": 2, "name": "Gmail", "price": 1000}
  ]
}</pre>

                <h5 class="mt-4">3. Lấy danh sách nhà mạng</h5>
                <div class="bg-light p-3 rounded">
                    <strong>GET</strong> <code>{{ base_url }}/network/get-network-by-api-key?api_key={{ api_key }}</code>
                </div>
                <pre class="bg-dark text-light p-3 mt-2 rounded">
{
  "status": 200,
  "data": [
    {"id": 1, "name": "VIETTEL"},
    {"id": 2, "name": "MOBIFONE"}
  ]
}</pre>

                <h5 class="mt-4">4. Lấy số điện thoại</h5>
                <div class="bg-light p-3 rounded">
                    <strong>GET</strong> <code>{{ base_url }}/sim/get_sim?service_id=1&api_key={{ api_key }}</code>
                </div>
                <pre class="bg-dark text-light p-3 mt-2 rounded">
{
  "status": 200,
  "data": {
    "otpId": 139126,
    "simId": 7280,
    "phone": "0569680819"
  }
}</pre>

                <h5 class="mt-4">5. Kiểm tra OTP</h5>
                <div class="bg-light p-3 rounded">
                    <strong>GET</strong> <code>{{ base_url }}/otp/get_otp_by_phone_api_key?otp_id=139126&api_key={{ api_key }}</code>
                </div>
                <pre class="bg-dark text-light p-3 mt-2 rounded">
{
  "status": 200,
  "data": {
    "code": "123446",
    "content": "H123446 gửi thông báo"
  }
}</pre>

                <h5 class="mt-4">6. Hủy số</h5>
                <div class="bg-light p-3 rounded">
                    <strong>GET</strong> <code>{{ base_url }}/sim/cancel_api_key/7280?api_key={{ api_key }}</code>
                </div>

                <h5 class="mt-4">7. Thuê lại số</h5>
                <div class="bg-light p-3 rounded">
                    <strong>GET</strong> <code>{{ base_url }}/sim/reuse_by_phone_api_key?phone=0569680819&service_id=3&api_key={{ api_key }}</code>
                </div>
            </div>
        </div>
    </div>
</div>
'''

# USERS TEMPLATE
USERS_TEMPLATE = '''
<div class="card">
    <div class="card-header"><h5><i class="bi bi-people"></i> Quản lý người dùng</h5></div>
    <div class="card-body">
        <div class="row mb-3">
            <div class="col-md-6"><input type="text" class="search-box" id="searchInput" placeholder="🔍 Tìm kiếm..."></div>
            <div class="col-md-6 text-end"><button class="btn btn-success" onclick="exportToExcel()"><i class="bi bi-file-excel"></i> Xuất Excel</button></div>
        </div>
        <table class="table table-striped" id="usersTable">
            <thead><tr><th>ID</th><th>User ID</th><th>Username</th><th>Số dư</th><th>Đã thuê</th><th>Tổng chi</th><th>Lợi nhuận</th><th>Ngày tạo</th><th>Trạng thái</th><th>Thao tác</th></tr></thead>
            <tbody>
                {% for user in users %}
                <tr>
                    <td>{{ user.id }}</td><td><code>{{ user.user_id }}</code></td><td>@{{ user.username or 'N/A' }}</td>
                    <td>{{ "{:,.0f}".format(user.balance) }}đ</td><td>{{ user.total_rentals }}</td><td>{{ "{:,.0f}".format(user.total_spent) }}đ</td>
                    <td class="text-success">{{ "{:,.0f}".format(user.profit or 0) }}đ</td><td>{{ user.created_at.strftime('%d/%m/%Y') }}</td>
                    <td><span class="badge bg-{{ 'danger' if user.is_banned else 'success' }}">{{ 'Bị khóa' if user.is_banned else 'Hoạt động' }}</span></td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="addMoney({{ user.user_id }})"><i class="bi bi-plus-circle"></i> Cộng tiền</button>
                        <button class="btn btn-sm btn-{{ 'success' if user.is_banned else 'danger' }}" onclick="toggleBan({{ user.user_id }})">
                            <i class="bi bi-{{ 'unlock' if user.is_banned else 'lock' }}"></i> {{ 'Mở khóa' if user.is_banned else 'Khóa' }}
                        </button>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<!-- Modal cộng tiền -->
<div class="modal fade" id="addMoneyModal" tabindex="-1">
    <div class="modal-dialog"><div class="modal-content">
        <div class="modal-header"><h5 class="modal-title">Cộng tiền thủ công</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
        <form id="addMoneyForm">
            <div class="modal-body">
                <input type="hidden" name="user_id" id="modal_user_id">
                <div class="mb-3"><label class="form-label">Số tiền</label><input type="number" class="form-control" name="amount" min="1000" step="1000" required></div>
                <div class="mb-3"><label class="form-label">Lý do</label><input type="text" class="form-control" name="reason" value="Cộng tiền thủ công"></div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Hủy</button>
                <button type="submit" class="btn btn-primary">Xác nhận</button>
            </div>
        </form>
    </div></div>
</div>

<script>
function addMoney(userId) {
    document.getElementById('modal_user_id').value = userId;
    new bootstrap.Modal(document.getElementById('addMoneyModal')).show();
}

document.getElementById('addMoneyForm').addEventListener('submit', function(e) {
    e.preventDefault();
    fetch('/add_money', {
        method: 'POST',
        headers: {'Content-Type': 'application/x-www-form-urlencoded'},
        body: new URLSearchParams(new FormData(this))
    }).then(() => location.reload());
});

function toggleBan(userId) {
    if(confirm('Thay đổi trạng thái user?')) {
        fetch('/toggle_ban', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: userId})
        }).then(() => location.reload());
    }
}

function exportToExcel() { window.location.href = '/export_users'; }

document.getElementById('searchInput').addEventListener('keyup', function() {
    let search = this.value.toLowerCase();
    document.querySelectorAll('#usersTable tbody tr').forEach(row => {
        row.style.display = row.textContent.toLowerCase().includes(search) ? '' : 'none';
    });
});
</script>
'''

# PROFIT TEMPLATE
PROFIT_TEMPLATE = '''
<div class="row">
    <div class="col-md-12">
        <div class="card">
            <div class="card-header"><h5><i class="bi bi-graph-up-arrow"></i> Báo cáo lợi nhuận</h5></div>
            <div class="card-body">
                <ul class="nav nav-tabs mb-3">
                    <li class="nav-item"><a class="nav-link {% if period == 'today' %}active{% endif %}" href="?period=today">Hôm nay</a></li>
                    <li class="nav-item"><a class="nav-link {% if period == 'week' %}active{% endif %}" href="?period=week">Tuần này</a></li>
                    <li class="nav-item"><a class="nav-link {% if period == 'month' %}active{% endif %}" href="?period=month">Tháng này</a></li>
                    <li class="nav-item"><a class="nav-link {% if period == 'all' %}active{% endif %}" href="?period=all">Tất cả</a></li>
                </ul>
            </div>
        </div>
    </div>
</div>

<div class="row mt-4">
    <div class="col-md-3"><div class="stat-card"><i class="bi bi-cash" style="font-size:40px; color:#28a745;"></i><div class="stat-number">{{ "{:,.0f}".format(profit.total_revenue) }}đ</div><div class="stat-label">Doanh thu</div></div></div>
    <div class="col-md-3"><div class="stat-card"><i class="bi bi-cash-stack" style="font-size:40px; color:#dc3545;"></i><div class="stat-number">{{ "{:,.0f}".format(profit.total_cost) }}đ</div><div class="stat-label">Chi phí</div></div></div>
    <div class="col-md-3"><div class="stat-card"><i class="bi bi-graph-up-arrow" style="font-size:40px; color:#28a745;"></i><div class="profit-number">{{ "{:,.0f}".format(profit.net_profit) }}đ</div><div class="stat-label">Lợi nhuận</div></div></div>
    <div class="col-md-3"><div class="stat-card"><i class="bi bi-percent" style="font-size:40px; color:#667eea;"></i><div class="stat-number">{{ "{:.1f}".format(profit.profit_margin) }}%</div><div class="stat-label">Biên lợi nhuận</div></div></div>
</div>

<div class="card mt-4">
    <div class="card-header"><h5><i class="bi bi-pie-chart"></i> Lợi nhuận theo dịch vụ</h5></div>
    <div class="card-body">
        <table class="table table-striped">
            <thead><tr><th>Dịch vụ</th><th>Số lượt</th><th>Doanh thu</th><th>Chi phí</th><th>Lợi nhuận</th><th>Biên LN</th></tr></thead>
            <tbody>
                {% for service in profit.by_service %}
                <tr>
                    <td>{{ service.name }}</td><td>{{ service.count }}</td><td>{{ "{:,.0f}".format(service.revenue) }}đ</td>
                    <td>{{ "{:,.0f}".format(service.cost) }}đ</td>
                    <td class="text-success">{{ "{:,.0f}".format(service.profit) }}đ</td>
                    <td><span class="badge bg-{{ 'success' if service.margin >= 30 else 'warning' if service.margin >= 10 else 'danger' }}">{{ "{:.1f}".format(service.margin) }}%</span></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
'''

# TRANSACTIONS TEMPLATE (ĐÃ SỬA LỖI)
TRANSACTIONS_TEMPLATE = '''
<div class="card">
    <div class="card-header"><h5><i class="bi bi-cash-stack"></i> Lịch sử giao dịch</h5></div>
    <div class="card-body">
        <ul class="nav nav-tabs mb-3">
            <li class="nav-item"><a class="nav-link {% if tab == 'all' %}active{% endif %}" href="?tab=all">Tất cả</a></li>
            <li class="nav-item"><a class="nav-link {% if tab == 'deposit' %}active{% endif %}" href="?tab=deposit">Nạp tiền</a></li>
            <li class="nav-item"><a class="nav-link {% if tab == 'rental' %}active{% endif %}" href="?tab=rental">Thuê số</a></li>
            <li class="nav-item"><a class="nav-link {% if tab == 'manual' %}active{% endif %}" href="?tab=manual">Cộng thủ công</a></li>
        </ul>
        <table class="table table-striped">
            <thead><tr><th>Thời gian</th><th>User</th><th>Loại</th><th>Dịch vụ</th><th>Số tiền</th><th>Lợi nhuận</th><th>Mã GD</th><th>Trạng thái</th></tr></thead>
            <tbody>
                {% for trans in transactions %}
                <tr>
                    <td>{{ trans.time }}</td><td><code>{{ trans.user_id }}</code></td>
                    <td><span class="badge bg-{{ 'success' if trans.type == 'deposit' else 'primary' }}">{{ 'Nạp tiền' if trans.type == 'deposit' else 'Thuê số' }}</span></td>
                    <td>{{ trans.service or '-' }}</td><td>{{ "{:,.0f}".format(trans.amount) }}đ</td>
                    <td class="text-success">{{ "{:,.0f}".format(trans.profit) }}đ</td>
                    <td><code>{{ trans.code }}</code></td>
                    <td><span class="badge bg-success">Thành công</span></td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
'''

# MANUAL TEMPLATE
MANUAL_TEMPLATE = '''
<div class="row">
    <div class="col-md-8 mx-auto">
        <div class="card">
            <div class="card-header"><h5><i class="bi bi-plus-circle"></i> Cộng tiền thủ công</h5></div>
            <div class="card-body">
                <form method="POST" action="/add_money">
                    <div class="mb-3">
                        <label class="form-label">User ID</label>
                        <input type="number" class="form-control" name="user_id" required placeholder="5180190297">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Số tiền</label>
                        <input type="number" class="form-control" name="amount" min="1000" step="1000" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Lý do</label>
                        <input type="text" class="form-control" name="reason" value="Cộng tiền thủ công">
                    </div>
                    <button type="submit" class="btn btn-primary w-100"><i class="bi bi-check-circle"></i> Xác nhận</button>
                </form>
            </div>
        </div>
    </div>
</div>
'''

# STATISTICS TEMPLATE
STATISTICS_TEMPLATE = '''
<div class="card">
    <div class="card-header"><h5><i class="bi bi-bar-chart"></i> Thống kê chi tiết</h5></div>
    <div class="card-body">
        <ul class="nav nav-tabs mb-3">
            <li class="nav-item"><a class="nav-link {% if stat_type == 'daily' %}active{% endif %}" href="?type=daily">Theo ngày</a></li>
            <li class="nav-item"><a class="nav-link {% if stat_type == 'weekly' %}active{% endif %}" href="?type=weekly">Theo tuần</a></li>
            <li class="nav-item"><a class="nav-link {% if stat_type == 'monthly' %}active{% endif %}" href="?type=monthly">Theo tháng</a></li>
        </ul>
        <table class="table table-striped">
            <thead><tr><th>Thời gian</th><th>Nạp tiền</th><th>Thuê số</th><th>Chi phí</th><th>Lợi nhuận</th><th>GD</th></tr></thead>
            <tbody>
                {% for stat in stats_data %}
                <tr>
                    <td>{{ stat.period }}</td><td>{{ "{:,.0f}".format(stat.deposit) }}đ</td><td>{{ "{:,.0f}".format(stat.rental) }}đ</td>
                    <td>{{ "{:,.0f}".format(stat.cost) }}đ</td><td class="text-success">{{ "{:,.0f}".format(stat.profit) }}đ</td><td>{{ stat.count }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>
'''

# === ROUTES ===

@app.route('/')
def index():
    now = datetime.now()
    with app.app_context():
        total_users = User.query.count()
        new_users = User.query.filter(User.created_at >= now - timedelta(days=1)).count()
        
        transactions = Transaction.query.all()
        rentals = Rental.query.all()
        
        deposit_total = sum(t.amount for t in transactions if t.type == 'deposit' and t.status == 'success')
        rental_total = sum(r.price_charged for r in rentals if r.status == 'success')
        api_cost = sum(r.cost or 0 for r in rentals if r.status == 'success')
        profit = rental_total - api_cost
        
        recent = []
        all_items = list(transactions) + list(rentals)
        all_items.sort(key=lambda x: x.created_at, reverse=True)
        
        for item in all_items[:10]:
            if hasattr(item, 'type'):
                recent.append({
                    'time': item.created_at.strftime('%H:%M %d/%m'),
                    'user_id': item.user_id,
                    'type': 'Nạp tiền',
                    'service': None,
                    'amount': item.amount,
                    'profit': 0
                })
            else:
                profit_item = item.price_charged - (item.cost or (item.price_charged - 1000))
                recent.append({
                    'time': item.created_at.strftime('%H:%M %d/%m'),
                    'user_id': item.user_id,
                    'type': 'Thuê số',
                    'service': item.service_name,
                    'amount': item.price_charged,
                    'profit': profit_item
                })
        
        stats = {
            'total_users': total_users,
            'new_users': new_users,
            'total_orders': len(rentals),
            'success_orders': len([r for r in rentals if r.status == 'success']),
            'revenue': deposit_total + rental_total,
            'deposit': deposit_total,
            'rental': rental_total,
            'cost': api_cost,
            'service_fee': rental_total - api_cost,
            'profit': profit,
            'profit_margin': (profit / rental_total * 100) if rental_total > 0 else 0,
            'recent_transactions': recent
        }
    
    return render_template_string(
        BASE_TEMPLATE.replace('{% block content %}{% endblock %}', INDEX_TEMPLATE),
        stats=stats,
        now=now
    )

@app.route('/web-deposit')
def web_deposit():
    return render_template_string(
        BASE_TEMPLATE.replace('{% block content %}{% endblock %}', WEB_DEPOSIT_TEMPLATE),
        now=datetime.now()
    )

@app.route('/web-deposit', methods=['POST'])
def web_deposit_post():
    user_id = request.form.get('user_id', type=int)
    amount = request.form.get('amount', type=int)
    method = request.form.get('method')
    
    flash(f'✅ Yêu cầu nạp {amount:,}đ qua {method} đã được tạo. Vui lòng chờ xử lý.', 'success')
    return redirect('/web-deposit')

@app.route('/api-docs')
def api_docs():
    # Lấy số dư từ API
    balance = 0
    try:
        response = requests.get(f"{BASE_URL}/yourself/information-by-api-key?api_key={API_KEY}")
        if response.status_code == 200:
            data = response.json()
            if data.get('status') == 200:
                balance = data.get('data', {}).get('balance', 0)
    except:
        pass
    
    return render_template_string(
        BASE_TEMPLATE.replace('{% block content %}{% endblock %}', API_DOCS_TEMPLATE),
        api_key=API_KEY,
        base_url=BASE_URL,
        balance=balance,
        now=datetime.now()
    )

@app.route('/users')
def users():
    with app.app_context():
        users_list = User.query.order_by(User.created_at.desc()).all()
        users_with_profit = []
        
        for u in users_list:
            user_rentals = Rental.query.filter_by(user_id=u.id, status='success').all()
            profit = sum(r.price_charged - (r.cost or (r.price_charged - 1000)) for r in user_rentals)
            
            users_with_profit.append({
                'id': u.id,
                'user_id': u.user_id,
                'username': u.username,
                'balance': u.balance,
                'total_rentals': u.total_rentals,
                'total_spent': u.total_spent,
                'created_at': u.created_at,
                'is_banned': u.is_banned,
                'profit': profit
            })
    
    return render_template_string(
        BASE_TEMPLATE.replace('{% block content %}{% endblock %}', USERS_TEMPLATE),
        users=users_with_profit,
        now=datetime.now()
    )

@app.route('/profit')
def profit():
    period = request.args.get('period', 'today')
    now = datetime.now()
    
    if period == 'today':
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1)
    elif period == 'week':
        start = now - timedelta(days=now.weekday())
        start = datetime(start.year, start.month, start.day)
        end = start + timedelta(days=7)
    elif period == 'month':
        start = datetime(now.year, now.month, 1)
        end = datetime(now.year, now.month + 1, 1) if now.month < 12 else datetime(now.year + 1, 1, 1)
    else:
        start = datetime(2020, 1, 1)
        end = now + timedelta(days=1)
    
    with app.app_context():
        rentals = Rental.query.filter(
            Rental.status == 'success',
            Rental.created_at >= start,
            Rental.created_at < end
        ).all()
        
        total_revenue = sum(r.price_charged for r in rentals)
        total_cost = sum(r.cost or (r.price_charged - 1000) for r in rentals)
        net_profit = total_revenue - total_cost
        profit_margin = (net_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        service_stats = defaultdict(lambda: {'count': 0, 'revenue': 0, 'cost': 0})
        for r in rentals:
            service_stats[r.service_name]['count'] += 1
            service_stats[r.service_name]['revenue'] += r.price_charged
            service_stats[r.service_name]['cost'] += r.cost or (r.price_charged - 1000)
        
        by_service = []
        for name, data in service_stats.items():
            profit = data['revenue'] - data['cost']
            margin = (profit / data['revenue'] * 100) if data['revenue'] > 0 else 0
            by_service.append({
                'name': name,
                'count': data['count'],
                'revenue': data['revenue'],
                'cost': data['cost'],
                'profit': profit,
                'margin': margin
            })
        
        profit_data = {
            'total_revenue': total_revenue,
            'total_cost': total_cost,
            'net_profit': net_profit,
            'profit_margin': profit_margin,
            'by_service': sorted(by_service, key=lambda x: x['profit'], reverse=True)
        }
    
    return render_template_string(
        BASE_TEMPLATE.replace('{% block content %}{% endblock %}', PROFIT_TEMPLATE),
        profit=profit_data,
        now=now,
        period=period
    )

@app.route('/transactions')
def transactions():
    tab = request.args.get('tab', 'all')
    
    with app.app_context():
        if tab == 'deposit':
            trans = Transaction.query.filter_by(type='deposit').order_by(Transaction.created_at.desc()).limit(100).all()
            rentals = []
        elif tab == 'rental':
            trans = []
            rentals = Rental.query.order_by(Rental.created_at.desc()).limit(100).all()
        elif tab == 'manual':
            trans = Transaction.query.filter(Transaction.description.like('%thủ công%')).order_by(Transaction.created_at.desc()).limit(100).all()
            rentals = []
        else:
            trans = Transaction.query.order_by(Transaction.created_at.desc()).limit(50).all()
            rentals = Rental.query.order_by(Rental.created_at.desc()).limit(50).all()
        
        transactions_list = []
        for t in trans:
            transactions_list.append({
                'time': t.created_at.strftime('%H:%M %d/%m/%Y'),
                'user_id': t.user_id,
                'type': 'deposit',
                'service': None,
                'amount': t.amount,
                'profit': 0,
                'code': t.transaction_code,
                'status': t.status
            })
        for r in rentals:
            profit = r.price_charged - (r.cost or (r.price_charged - 1000))
            # SỬA LỖI: Dùng transaction_code nếu có, nếu không thì dùng otp_id hoặc tạo mã giả
            code = r.transaction_code if hasattr(r, 'transaction_code') and r.transaction_code else f"RENTAL_{r.id}_{r.created_at.strftime('%Y%m%d%H%M%S')}"
            transactions_list.append({
                'time': r.created_at.strftime('%H:%M %d/%m/%Y'),
                'user_id': r.user_id,
                'type': 'rental',
                'service': r.service_name,
                'amount': r.price_charged,
                'profit': profit,
                'code': code,
                'status': r.status
            })
        
        transactions_list.sort(key=lambda x: x['time'], reverse=True)
    
    return render_template_string(
        BASE_TEMPLATE.replace('{% block content %}{% endblock %}', TRANSACTIONS_TEMPLATE),
        transactions=transactions_list,
        tab=tab,
        now=datetime.now()
    )

@app.route('/statistics')
def statistics():
    stat_type = request.args.get('type', 'daily')
    now = datetime.now()
    stats_data = []
    
    with app.app_context():
        if stat_type == 'daily':
            for i in range(6, -1, -1):
                date = datetime(now.year, now.month, now.day) - timedelta(days=i)
                next_date = date + timedelta(days=1)
                
                deposit = sum(t.amount for t in Transaction.query.filter(
                    Transaction.type == 'deposit',
                    Transaction.status == 'success',
                    Transaction.created_at >= date,
                    Transaction.created_at < next_date
                ).all())
                
                rentals = Rental.query.filter(
                    Rental.status == 'success',
                    Rental.created_at >= date,
                    Rental.created_at < next_date
                ).all()
                
                rental = sum(r.price_charged for r in rentals)
                cost = sum(r.cost or (r.price_charged - 1000) for r in rentals)
                count = len(rentals) + Transaction.query.filter(
                    Transaction.created_at >= date,
                    Transaction.created_at < next_date
                ).count()
                
                stats_data.append({
                    'period': date.strftime('%d/%m'),
                    'deposit': deposit,
                    'rental': rental,
                    'cost': cost,
                    'profit': rental - cost,
                    'count': count
                })
        
        elif stat_type == 'weekly':
            for i in range(3, -1, -1):
                start_week = (now - timedelta(weeks=i)).replace(hour=0, minute=0, second=0, microsecond=0)
                start_week = start_week - timedelta(days=start_week.weekday())
                end_week = start_week + timedelta(days=7)
                
                deposit = sum(t.amount for t in Transaction.query.filter(
                    Transaction.type == 'deposit',
                    Transaction.status == 'success',
                    Transaction.created_at >= start_week,
                    Transaction.created_at < end_week
                ).all())
                
                rentals = Rental.query.filter(
                    Rental.status == 'success',
                    Rental.created_at >= start_week,
                    Rental.created_at < end_week
                ).all()
                
                rental = sum(r.price_charged for r in rentals)
                cost = sum(r.cost or (r.price_charged - 1000) for r in rentals)
                count = len(rentals) + Transaction.query.filter(
                    Transaction.created_at >= start_week,
                    Transaction.created_at < end_week
                ).count()
                
                stats_data.append({
                    'period': f'Tuần {i+1}',
                    'deposit': deposit,
                    'rental': rental,
                    'cost': cost,
                    'profit': rental - cost,
                    'count': count
                })
    
    return render_template_string(
        BASE_TEMPLATE.replace('{% block content %}{% endblock %}', STATISTICS_TEMPLATE),
        stats_data=stats_data,
        stat_type=stat_type,
        now=now
    )

@app.route('/manual')
def manual():
    with app.app_context():
        manual_trans = Transaction.query.filter(
            Transaction.description.like('%thủ công%')
        ).order_by(Transaction.created_at.desc()).limit(10).all()
        
        manual_list = []
        for t in manual_trans:
            user = User.query.get(t.user_id)
            manual_list.append({
                'time': t.created_at.strftime('%H:%M %d/%m/%Y'),
                'user_id': user.user_id if user else 'N/A',
                'amount': t.amount,
                'reason': t.description
            })
    
    return render_template_string(
        BASE_TEMPLATE.replace('{% block content %}{% endblock %}', MANUAL_TEMPLATE + '''
        <div class="card mt-4">
            <div class="card-header"><h5>Lịch sử cộng tiền</h5></div>
            <div class="card-body">
                <table class="table table-sm">
                    <thead><tr><th>Thời gian</th><th>User</th><th>Số tiền</th><th>Lý do</th></tr></thead>
                    <tbody>
                        {% for trans in manual_transactions %}
                        <tr><td>{{ trans.time }}</td><td><code>{{ trans.user_id }}</code></td><td class="text-success">+{{ "{:,.0f}".format(trans.amount) }}đ</td><td>{{ trans.reason }}</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        '''),
        manual_transactions=manual_list,
        now=datetime.now()
    )

@dashboard_bp.route('/add_money', methods=['POST'])
def add_money():
    """API cộng tiền thủ công - ĐÃ FIX LỖI CỘNG TIỀN"""
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
        
        # Lưu số dư cũ
        old_balance = user.balance
        
        # CỘNG TIỀN - DÒNG QUAN TRỌNG NHẤT!
        user.balance += amount
        
        # Tạo transaction code
        transaction_code = f"MANUAL_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Tạo transaction
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
        
        # Refresh để lấy số dư mới nhất
        db.session.refresh(user)
        
        # Đồng bộ lên Render
        try:
            import requests
            RENDER_URL = "https://bot-thue-sms-v2.onrender.com"
            requests.post(f"{RENDER_URL}/api/check-user", json={'user_id': user.user_id, 'username': user.username}, timeout=3)
            requests.post(f"{RENDER_URL}/api/sync-pending", json={'transactions': [{'code': transaction_code, 'amount': amount, 'user_id': user.user_id, 'username': user.username}]}, timeout=3)
        except:
            pass
        
        logger.info(f"✅ ĐÃ CỘNG {amount}đ CHO USER {user_id}")
        logger.info(f"   Số dư: {old_balance}đ → {user.balance}đ")
        
        flash(f'💰 NẠP TIỀN THÀNH CÔNG!\n'
              f'• Số tiền: {amount:,}đ\n'
              f'• Mã GD: {transaction_code}\n'
              f'• Số dư mới: {user.balance:,}đ', 'success')
    
    return redirect(url_for('dashboard.manual'))

@app.route('/toggle_ban', methods=['POST'])
def toggle_ban():
    data = request.get_json()
    user_id = data.get('user_id')
    
    with app.app_context():
        user = User.query.filter_by(user_id=user_id).first()
        if user:
            user.is_banned = not user.is_banned
            db.session.commit()
            return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/export_users')
def export_users():
    import csv
    from flask import Response
    import io
    
    with app.app_context():
        users = User.query.all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'User ID', 'Username', 'Số dư', 'Đã thuê', 'Tổng chi', 'Ngày tạo'])
        
        for u in users:
            writer.writerow([u.id, u.user_id, u.username or '', u.balance, u.total_rentals, u.total_spent, u.created_at])
        
        output.seek(0)
        return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment;filename=users.csv'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)