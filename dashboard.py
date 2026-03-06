from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
from database.models import db, User, Transaction, Rental
from datetime import datetime, timedelta
import os
import plotly.graph_objs as go
import plotly.utils
import json
from collections import defaultdict
import secrets
import logging

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Cấu hình database
db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database', 'bot.db')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

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
        body { 
            background: #f8f9fa;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .navbar { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .navbar-brand, .nav-link { 
            color: white !important; 
            font-weight: 500;
        }
        .nav-link:hover {
            background: rgba(255,255,255,0.1);
            border-radius: 5px;
        }
        .card { 
            border-radius: 15px; 
            box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
            margin-bottom: 20px;
            border: none;
        }
        .card-header { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
            color: white; 
            border-radius: 15px 15px 0 0 !important;
            font-weight: 600;
            padding: 15px 20px;
        }
        .stat-card { 
            background: white; 
            padding: 25px; 
            border-radius: 15px; 
            text-align: center;
            transition: transform 0.3s;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .stat-card:hover {
            transform: translateY(-5px);
        }
        .stat-number { 
            font-size: 36px; 
            font-weight: bold; 
            color: #667eea; 
        }
        .stat-label { 
            color: #666; 
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        .table thead { 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .table thead th {
            border: none;
        }
        .btn-period { 
            margin: 0 5px; 
            border-radius: 20px;
            padding: 5px 15px;
        }
        .active-period { 
            background: #667eea; 
            color: white; 
            border-color: #667eea;
        }
        .total-revenue { 
            font-size: 48px; 
            font-weight: bold; 
            color: #28a745; 
        }
        .search-box {
            border-radius: 20px;
            padding: 8px 15px;
            border: 1px solid #ddd;
            width: 100%;
        }
        .modal-content {
            border-radius: 15px;
        }
        .flash-message {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            animation: slideIn 0.5s;
        }
        @keyframes slideIn {
            from {
                transform: translateX(100%);
            }
            to {
                transform: translateX(0);
            }
        }
    </style>
</head>
<body>
    <!-- Flash messages -->
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }} alert-dismissible fade show flash-message" role="alert">
                    {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}
        {% endif %}
    {% endwith %}

    <nav class="navbar navbar-expand-lg navbar-dark">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">
                <i class="bi bi-graph-up"></i> Bot Thuê SMS - Quản Lý
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('index') }}">
                            <i class="bi bi-house-door"></i> Dashboard
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('users') }}">
                            <i class="bi bi-people"></i> Người dùng
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('transactions') }}">
                            <i class="bi bi-cash-stack"></i> Giao dịch
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('manual') }}">
                            <i class="bi bi-plus-circle"></i> Cộng tiền thủ công
                        </a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="{{ url_for('statistics') }}">
                            <i class="bi bi-bar-chart"></i> Thống kê
                        </a>
                    </li>
                    <li class="nav-item">
                        <span class="nav-link">
                            <i class="bi bi-clock"></i> {{ now.strftime('%H:%M %d/%m/%Y') }}
                        </span>
                    </li>
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
            <div class="card-header">
                <h5 class="mb-0"><i class="bi bi-calendar"></i> Thống kê theo thời gian</h5>
            </div>
            <div class="card-body">
                <ul class="nav nav-tabs mb-3">
                    <li class="nav-item">
                        <a class="nav-link {% if period == 'today' %}active{% endif %}" href="?period=today">Hôm nay</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link {% if period == 'yesterday' %}active{% endif %}" href="?period=yesterday">Hôm qua</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link {% if period == 'week' %}active{% endif %}" href="?period=week">Tuần này</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link {% if period == 'month' %}active{% endif %}" href="?period=month">Tháng này</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link {% if period == 'last_month' %}active{% endif %}" href="?period=last_month">Tháng trước</a>
                    </li>
                </ul>
            </div>
        </div>
    </div>
</div>

<!-- Thống kê tổng quan -->
<div class="row mt-4">
    <div class="col-md-3">
        <div class="stat-card">
            <i class="bi bi-people" style="font-size: 40px; color: #667eea;"></i>
            <div class="stat-number">{{ "{:,.0f}".format(stats.total_users) }}</div>
            <div class="stat-label">Tổng người dùng</div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="stat-card">
            <i class="bi bi-person-plus" style="font-size: 40px; color: #28a745;"></i>
            <div class="stat-number">{{ "{:,.0f}".format(stats.new_users) }}</div>
            <div class="stat-label">Người dùng mới</div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="stat-card">
            <i class="bi bi-cart" style="font-size: 40px; color: #fd7e14;"></i>
            <div class="stat-number">{{ "{:,.0f}".format(stats.total_orders) }}</div>
            <div class="stat-label">Tổng số thuê</div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="stat-card">
            <i class="bi bi-check-circle" style="font-size: 40px; color: #28a745;"></i>
            <div class="stat-number">{{ "{:,.0f}".format(stats.success_orders) }}</div>
            <div class="stat-label">Thành công</div>
        </div>
    </div>
</div>

<!-- Doanh thu -->
<div class="row mt-4">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0"><i class="bi bi-cash"></i> Doanh thu</h5>
            </div>
            <div class="card-body text-center">
                <div class="total-revenue">{{ "{:,.0f}".format(stats.revenue) }}đ</div>
                <p class="text-muted">Tổng doanh thu trong kỳ</p>
                <div class="row mt-4">
                    <div class="col-6">
                        <h6><i class="bi bi-arrow-up-circle text-success"></i> Nạp tiền</h6>
                        <h4 class="text-success">{{ "{:,.0f}".format(stats.deposit) }}đ</h4>
                    </div>
                    <div class="col-6">
                        <h6><i class="bi bi-arrow-down-circle text-primary"></i> Thuê số</h6>
                        <h4 class="text-primary">{{ "{:,.0f}".format(stats.rental) }}đ</h4>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0"><i class="bi bi-graph-up"></i> Biểu đồ doanh thu</h5>
            </div>
            <div class="card-body">
                <div id="revenueChart"></div>
            </div>
        </div>
    </div>
</div>

<!-- Top người dùng và dịch vụ -->
<div class="row mt-4">
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0"><i class="bi bi-trophy"></i> Top người dùng</h5>
            </div>
            <div class="card-body">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>User ID</th>
                            <th>Username</th>
                            <th>Số lần thuê</th>
                            <th>Tổng chi</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for user in stats.top_users %}
                        <tr>
                            <td><code>{{ user.user_id }}</code></td>
                            <td>@{{ user.username or 'N/A' }}</td>
                            <td>{{ user.rentals }}</td>
                            <td>{{ "{:,.0f}".format(user.spent) }}đ</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    <div class="col-md-6">
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0"><i class="bi bi-fire"></i> Dịch vụ phổ biến</h5>
            </div>
            <div class="card-body">
                <table class="table table-hover">
                    <thead>
                        <tr>
                            <th>Dịch vụ</th>
                            <th>Số lượt thuê</th>
                            <th>Doanh thu</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for service in stats.top_services %}
                        <tr>
                            <td>{{ service.name }}</td>
                            <td>{{ service.count }}</td>
                            <td>{{ "{:,.0f}".format(service.revenue) }}đ</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<!-- Giao dịch gần đây -->
<div class="card mt-4">
    <div class="card-header">
        <h5 class="mb-0"><i class="bi bi-clock-history"></i> Giao dịch gần đây</h5>
    </div>
    <div class="card-body">
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>Thời gian</th>
                    <th>User ID</th>
                    <th>Loại</th>
                    <th>Dịch vụ</th>
                    <th>Số tiền</th>
                    <th>Trạng thái</th>
                </tr>
            </thead>
            <tbody>
                {% for trans in stats.recent_transactions %}
                <tr>
                    <td>{{ trans.time }}</td>
                    <td><code>{{ trans.user_id }}</code></td>
                    <td>
                        {% if trans.type == 'Nạp tiền' %}
                            <span class="badge bg-success">{{ trans.type }}</span>
                        {% else %}
                            <span class="badge bg-primary">{{ trans.type }}</span>
                        {% endif %}
                    </td>
                    <td>{{ trans.service or '-' }}</td>
                    <td>{{ "{:,.0f}".format(trans.amount) }}đ</td>
                    <td>
                        {% if trans.status == 'success' %}
                            <span class="badge bg-success">Thành công</span>
                        {% elif trans.status == 'pending' %}
                            <span class="badge bg-warning">Chờ</span>
                        {% else %}
                            <span class="badge bg-danger">Thất bại</span>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<script>
    // Vẽ biểu đồ doanh thu
    var revenueData = {{ revenue_chart | safe }};
    Plotly.newPlot('revenueChart', revenueData.data, revenueData.layout);
</script>
'''

# USERS TEMPLATE
USERS_TEMPLATE = '''
<div class="card">
    <div class="card-header">
        <h5 class="mb-0"><i class="bi bi-people"></i> Quản lý người dùng</h5>
    </div>
    <div class="card-body">
        <div class="row mb-3">
            <div class="col-md-6">
                <input type="text" class="search-box" id="searchInput" placeholder="🔍 Tìm kiếm theo ID hoặc username...">
            </div>
            <div class="col-md-6 text-end">
                <button class="btn btn-success" onclick="exportToExcel()">
                    <i class="bi bi-file-excel"></i> Xuất Excel
                </button>
            </div>
        </div>
        
        <table class="table table-striped" id="usersTable">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>User ID</th>
                    <th>Username</th>
                    <th>Số dư</th>
                    <th>Đã thuê</th>
                    <th>Tổng chi</th>
                    <th>Ngày tạo</th>
                    <th>Trạng thái</th>
                    <th>Thao tác</th>
                </tr>
            </thead>
            <tbody>
                {% for user in users %}
                <tr>
                    <td>{{ user.id }}</td>
                    <td><code>{{ user.user_id }}</code></td>
                    <td>@{{ user.username or 'N/A' }}</td>
                    <td>{{ "{:,.0f}".format(user.balance) }}đ</td>
                    <td>{{ user.total_rentals }}</td>
                    <td>{{ "{:,.0f}".format(user.total_spent) }}đ</td>
                    <td>{{ user.created_at.strftime('%d/%m/%Y') }}</td>
                    <td>
                        {% if user.is_banned %}
                            <span class="badge bg-danger">Bị khóa</span>
                        {% else %}
                            <span class="badge bg-success">Hoạt động</span>
                        {% endif %}
                    </td>
                    <td>
                        <button class="btn btn-sm btn-primary" onclick="addMoney({{ user.user_id }})">
                            <i class="bi bi-plus-circle"></i> Cộng tiền
                        </button>
                        {% if user.is_banned %}
                            <button class="btn btn-sm btn-success" onclick="toggleBan({{ user.user_id }})">
                                <i class="bi bi-unlock"></i> Mở khóa
                            </button>
                        {% else %}
                            <button class="btn btn-sm btn-danger" onclick="toggleBan({{ user.user_id }})">
                                <i class="bi bi-lock"></i> Khóa
                            </button>
                        {% endif %}
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</div>

<!-- Modal cộng tiền -->
<div class="modal fade" id="addMoneyModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Cộng tiền thủ công</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <form action="{{ url_for('add_money') }}" method="POST">
                <div class="modal-body">
                    <input type="hidden" name="user_id" id="modal_user_id">
                    <div class="mb-3">
                        <label class="form-label">Số tiền (VNĐ)</label>
                        <input type="number" class="form-control" name="amount" min="1000" step="1000" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Lý do</label>
                        <input type="text" class="form-control" name="reason" value="Cộng tiền thủ công" required>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Hủy</button>
                    <button type="submit" class="btn btn-primary">Xác nhận</button>
                </div>
            </form>
        </div>
    </div>
</div>

<script>
    function addMoney(userId) {
        document.getElementById('modal_user_id').value = userId;
        new bootstrap.Modal(document.getElementById('addMoneyModal')).show();
    }
    
    function toggleBan(userId) {
        if (confirm('Bạn có chắc chắn muốn thay đổi trạng thái khóa của user này?')) {
            fetch('{{ url_for("toggle_ban") }}', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({user_id: userId})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    location.reload();
                } else {
                    alert('Có lỗi xảy ra: ' + data.message);
                }
            });
        }
    }
    
    function exportToExcel() {
        window.location.href = '{{ url_for("export_users") }}';
    }
    
    // Tìm kiếm
    document.getElementById('searchInput').addEventListener('keyup', function() {
        var searchText = this.value.toLowerCase();
        var tableRows = document.querySelectorAll('#usersTable tbody tr');
        
        tableRows.forEach(function(row) {
            var text = row.textContent.toLowerCase();
            row.style.display = text.includes(searchText) ? '' : 'none';
        });
    });
</script>
'''

# TRANSACTIONS TEMPLATE
TRANSACTIONS_TEMPLATE = '''
<div class="card">
    <div class="card-header">
        <h5 class="mb-0"><i class="bi bi-cash-stack"></i> Lịch sử giao dịch</h5>
    </div>
    <div class="card-body">
        <ul class="nav nav-tabs mb-3">
            <li class="nav-item">
                <a class="nav-link {% if tab == 'all' %}active{% endif %}" href="?tab=all">Tất cả</a>
            </li>
            <li class="nav-item">
                <a class="nav-link {% if tab == 'deposit' %}active{% endif %}" href="?tab=deposit">Nạp tiền</a>
            </li>
            <li class="nav-item">
                <a class="nav-link {% if tab == 'rental' %}active{% endif %}" href="?tab=rental">Thuê số</a>
            </li>
            <li class="nav-item">
                <a class="nav-link {% if tab == 'manual' %}active{% endif %}" href="?tab=manual">Cộng thủ công</a>
            </li>
        </ul>
        
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>Thời gian</th>
                    <th>User ID</th>
                    <th>Loại</th>
                    <th>Dịch vụ</th>
                    <th>Số tiền</th>
                    <th>Mã GD</th>
                    <th>Trạng thái</th>
                </tr>
            </thead>
            <tbody>
                {% for trans in transactions %}
                <tr>
                    <td>{{ trans.time }}</td>
                    <td><code>{{ trans.user_id }}</code></td>
                    <td>
                        {% if trans.type == 'deposit' %}
                            <span class="badge bg-success">Nạp tiền</span>
                        {% elif trans.type == 'rental' %}
                            <span class="badge bg-primary">Thuê số</span>
                        {% else %}
                            <span class="badge bg-info">{{ trans.type }}</span>
                        {% endif %}
                    </td>
                    <td>{{ trans.service or '-' }}</td>
                    <td>{{ "{:,.0f}".format(trans.amount) }}đ</td>
                    <td><code>{{ trans.code or '' }}</code></td>
                    <td>
                        {% if trans.status == 'success' %}
                            <span class="badge bg-success">Thành công</span>
                        {% elif trans.status == 'pending' %}
                            <span class="badge bg-warning">Chờ</span>
                        {% else %}
                            <span class="badge bg-danger">Thất bại</span>
                        {% endif %}
                    </td>
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
            <div class="card-header">
                <h5 class="mb-0"><i class="bi bi-plus-circle"></i> Cộng tiền thủ công</h5>
            </div>
            <div class="card-body">
                <form action="{{ url_for('add_money') }}" method="POST">
                    <div class="mb-3">
                        <label class="form-label">User ID (Telegram ID)</label>
                        <input type="number" class="form-control" name="user_id" required 
                               placeholder="Ví dụ: 5180190297">
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Số tiền (VNĐ)</label>
                        <input type="number" class="form-control" name="amount" min="1000" step="1000" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Lý do</label>
                        <input type="text" class="form-control" name="reason" value="Cộng tiền thủ công" required>
                    </div>
                    <button type="submit" class="btn btn-primary w-100">
                        <i class="bi bi-check-circle"></i> Xác nhận cộng tiền
                    </button>
                </form>
            </div>
        </div>
        
        <!-- Lịch sử cộng tiền thủ công gần đây -->
        <div class="card mt-4">
            <div class="card-header">
                <h5 class="mb-0"><i class="bi bi-clock-history"></i> Lịch sử cộng tiền thủ công</h5>
            </div>
            <div class="card-body">
                <table class="table table-sm">
                    <thead>
                        <tr>
                            <th>Thời gian</th>
                            <th>User</th>
                            <th>Số tiền</th>
                            <th>Lý do</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for trans in manual_transactions %}
                        <tr>
                            <td>{{ trans.time }}</td>
                            <td><code>{{ trans.user_id }}</code></td>
                            <td class="text-success">{{ "{:,.0f}".format(trans.amount) }}đ</td>
                            <td>{{ trans.reason }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>
'''

# STATISTICS TEMPLATE
STATISTICS_TEMPLATE = '''
<div class="row">
    <div class="col-md-12">
        <div class="card">
            <div class="card-header">
                <h5 class="mb-0"><i class="bi bi-bar-chart"></i> Thống kê chi tiết</h5>
            </div>
            <div class="card-body">
                <ul class="nav nav-tabs mb-3">
                    <li class="nav-item">
                        <a class="nav-link {% if stat_type == 'daily' %}active{% endif %}" href="?type=daily">Theo ngày</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link {% if stat_type == 'weekly' %}active{% endif %}" href="?type=weekly">Theo tuần</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link {% if stat_type == 'monthly' %}active{% endif %}" href="?type=monthly">Theo tháng</a>
                    </li>
                </ul>
                
                <div class="row">
                    <div class="col-md-12">
                        <div id="statsChart"></div>
                    </div>
                </div>
                
                <div class="row mt-4">
                    <div class="col-md-12">
                        <table class="table table-striped">
                            <thead>
                                <tr>
                                    <th>Thời gian</th>
                                    <th>Nạp tiền</th>
                                    <th>Thuê số</th>
                                    <th>Tổng doanh thu</th>
                                    <th>Số giao dịch</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for stat in stats_data %}
                                <tr>
                                    <td>{{ stat.period }}</td>
                                    <td>{{ "{:,.0f}".format(stat.deposit) }}đ</td>
                                    <td>{{ "{:,.0f}".format(stat.rental) }}đ</td>
                                    <td>{{ "{:,.0f}".format(stat.total) }}đ</td>
                                    <td>{{ stat.count }}</td>
                                </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
    var statsData = {{ stats_chart | safe }};
    Plotly.newPlot('statsChart', statsData.data, statsData.layout);
</script>
'''

# === ROUTES ===

@app.route('/')
def index():
    """Trang chính dashboard"""
    period = request.args.get('period', 'today')
    now = datetime.now()
    
    # Xác định khoảng thời gian
    if period == 'today':
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1)
    elif period == 'yesterday':
        start = datetime(now.year, now.month, now.day) - timedelta(days=1)
        end = start + timedelta(days=1)
    elif period == 'week':
        start = now - timedelta(days=now.weekday())
        start = datetime(start.year, start.month, start.day)
        end = start + timedelta(days=7)
    elif period == 'month':
        start = datetime(now.year, now.month, 1)
        if now.month == 12:
            end = datetime(now.year + 1, 1, 1)
        else:
            end = datetime(now.year, now.month + 1, 1)
    elif period == 'last_month':
        if now.month == 1:
            start = datetime(now.year - 1, 12, 1)
            end = datetime(now.year, 1, 1)
        else:
            start = datetime(now.year, now.month - 1, 1)
            end = datetime(now.year, now.month, 1)
    else:
        start = datetime(now.year, now.month, now.day)
        end = start + timedelta(days=1)
    
    with app.app_context():
        # Tổng số users
        total_users = User.query.count()
        
        # Users mới trong kỳ
        new_users = User.query.filter(User.created_at >= start, User.created_at < end).count()
        
        # Giao dịch trong kỳ
        transactions = Transaction.query.filter(Transaction.created_at >= start, Transaction.created_at < end).all()
        rentals = Rental.query.filter(Rental.created_at >= start, Rental.created_at < end).all()
        
        # Tính toán doanh thu
        deposit_total = sum(t.amount for t in transactions if t.type == 'deposit' and t.status == 'success')
        rental_total = sum(r.price_charged for r in rentals if r.status == 'success')
        
        # Thống kê theo ngày cho biểu đồ
        date_range = []
        current = start
        while current < end:
            date_range.append(current)
            current += timedelta(days=1)
        
        daily_revenue = []
        for date in date_range:
            next_date = date + timedelta(days=1)
            day_deposit = sum(t.amount for t in transactions 
                            if t.type == 'deposit' and t.status == 'success' 
                            and date <= t.created_at < next_date)
            day_rental = sum(r.price_charged for r in rentals 
                           if r.status == 'success' 
                           and date <= r.created_at < next_date)
            daily_revenue.append(day_deposit + day_rental)
        
        # Top users
        user_stats = defaultdict(lambda: {'rentals': 0, 'spent': 0, 'username': ''})
        for r in rentals:
            if r.status == 'success':
                user_stats[r.user_id]['rentals'] += 1
                user_stats[r.user_id]['spent'] += r.price_charged
        
        for u in User.query.all():
            if u.user_id in user_stats:
                user_stats[u.user_id]['username'] = u.username or 'N/A'
        
        top_users = sorted(
            [{'user_id': k, 'username': v['username'], 'rentals': v['rentals'], 'spent': v['spent']}
             for k, v in user_stats.items()],
            key=lambda x: x['spent'],
            reverse=True
        )[:5]
        
        # Top services
        service_stats = defaultdict(lambda: {'count': 0, 'revenue': 0})
        for r in rentals:
            if r.status == 'success':
                service_stats[r.service_name]['count'] += 1
                service_stats[r.service_name]['revenue'] += r.price_charged
        
        top_services = sorted(
            [{'name': k, 'count': v['count'], 'revenue': v['revenue']} 
             for k, v in service_stats.items()],
            key=lambda x: x['revenue'],
            reverse=True
        )[:5]
        
        # Giao dịch gần đây
        recent = []
        all_items = list(transactions) + list(rentals)
        all_items.sort(key=lambda x: x.created_at, reverse=True)
        
        for item in all_items[:10]:
            if hasattr(item, 'type'):  # Transaction
                recent.append({
                    'time': item.created_at.strftime('%H:%M %d/%m'),
                    'user_id': item.user_id,
                    'type': 'Nạp tiền' if item.type == 'deposit' else 'Rút',
                    'service': None,
                    'amount': item.amount,
                    'status': item.status
                })
            else:  # Rental
                recent.append({
                    'time': item.created_at.strftime('%H:%M %d/%m'),
                    'user_id': item.user_id,
                    'type': 'Thuê số',
                    'service': item.service_name,
                    'amount': item.price_charged,
                    'status': item.status
                })
        
        stats = {
            'total_users': total_users,
            'new_users': new_users,
            'total_orders': len(rentals),
            'success_orders': len([r for r in rentals if r.status == 'success']),
            'revenue': deposit_total + rental_total,
            'deposit': deposit_total,
            'rental': rental_total,
            'top_users': top_users,
            'top_services': top_services,
            'recent_transactions': recent
        }
        
        # Tạo biểu đồ
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[d.strftime('%d/%m') for d in date_range],
            y=daily_revenue,
            mode='lines+markers',
            name='Doanh thu',
            line=dict(color='#667eea', width=3)
        ))
        
        fig.update_layout(
            title=f'Doanh thu theo ngày',
            xaxis_title='Ngày',
            yaxis_title='Doanh thu (VNĐ)',
            template='plotly_white',
            height=400
        )
        
        revenue_chart = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    # Kết hợp template
    full_template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', INDEX_TEMPLATE)
    return render_template_string(
        full_template,
        stats=stats,
        revenue_chart=revenue_chart,
        now=now,
        period=period
    )

@app.route('/users')
def users():
    """Quản lý người dùng"""
    with app.app_context():
        users = User.query.order_by(User.created_at.desc()).all()
    
    full_template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', USERS_TEMPLATE)
    return render_template_string(
        full_template,
        users=users,
        now=datetime.now()
    )

@app.route('/transactions')
def transactions():
    """Xem lịch sử giao dịch"""
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
        
        transactions = []
        for t in trans:
            transactions.append({
                'time': t.created_at.strftime('%H:%M %d/%m/%Y'),
                'user_id': t.user_id,
                'type': 'deposit',
                'service': None,
                'amount': t.amount,
                'code': t.transaction_code,
                'status': t.status
            })
        for r in rentals:
            transactions.append({
                'time': r.created_at.strftime('%H:%M %d/%m/%Y'),
                'user_id': r.user_id,
                'type': 'rental',
                'service': r.service_name,
                'amount': r.price_charged,
                'code': r.otp_id,
                'status': r.status
            })
        
        transactions.sort(key=lambda x: x['time'], reverse=True)
    
    full_template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', TRANSACTIONS_TEMPLATE)
    return render_template_string(
        full_template,
        transactions=transactions,
        tab=tab,
        now=datetime.now()
    )

@app.route('/manual')
def manual():
    """Trang cộng tiền thủ công"""
    with app.app_context():
        manual_trans = Transaction.query.filter(
            Transaction.description.like('%thủ công%')
        ).order_by(Transaction.created_at.desc()).limit(20).all()
        
        manual_list = []
        for t in manual_trans:
            user = User.query.get(t.user_id)
            manual_list.append({
                'time': t.created_at.strftime('%H:%M %d/%m/%Y'),
                'user_id': user.user_id if user else 'N/A',
                'amount': t.amount,
                'reason': t.description
            })
    
    full_template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', MANUAL_TEMPLATE)
    return render_template_string(
        full_template,
        manual_transactions=manual_list,
        now=datetime.now()
    )

@app.route('/statistics')
def statistics():
    """Trang thống kê chi tiết"""
    stat_type = request.args.get('type', 'daily')
    now = datetime.now()
    
    stats_data = []
    dates = []
    deposit_data = []
    rental_data = []
    
    with app.app_context():
        if stat_type == 'daily':
            # 7 ngày gần nhất
            for i in range(6, -1, -1):
                date = datetime(now.year, now.month, now.day) - timedelta(days=i)
                next_date = date + timedelta(days=1)
                
                deposit = sum(t.amount for t in Transaction.query.filter(
                    Transaction.type == 'deposit',
                    Transaction.status == 'success',
                    Transaction.created_at >= date,
                    Transaction.created_at < next_date
                ).all())
                
                rental = sum(r.price_charged for r in Rental.query.filter(
                    Rental.status == 'success',
                    Rental.created_at >= date,
                    Rental.created_at < next_date
                ).all())
                
                count = Transaction.query.filter(
                    Transaction.created_at >= date,
                    Transaction.created_at < next_date
                ).count() + Rental.query.filter(
                    Rental.created_at >= date,
                    Rental.created_at < next_date
                ).count()
                
                stats_data.append({
                    'period': date.strftime('%d/%m/%Y'),
                    'deposit': deposit,
                    'rental': rental,
                    'total': deposit + rental,
                    'count': count
                })
                dates.append(date.strftime('%d/%m'))
                deposit_data.append(deposit)
                rental_data.append(rental)
        
        elif stat_type == 'weekly':
            # 4 tuần gần nhất
            for i in range(3, -1, -1):
                start_week = now - timedelta(weeks=i)
                start_week = start_week - timedelta(days=start_week.weekday())
                start_week = datetime(start_week.year, start_week.month, start_week.day)
                end_week = start_week + timedelta(days=7)
                
                deposit = sum(t.amount for t in Transaction.query.filter(
                    Transaction.type == 'deposit',
                    Transaction.status == 'success',
                    Transaction.created_at >= start_week,
                    Transaction.created_at < end_week
                ).all())
                
                rental = sum(r.price_charged for r in Rental.query.filter(
                    Rental.status == 'success',
                    Rental.created_at >= start_week,
                    Rental.created_at < end_week
                ).all())
                
                count = Transaction.query.filter(
                    Transaction.created_at >= start_week,
                    Transaction.created_at < end_week
                ).count() + Rental.query.filter(
                    Rental.created_at >= start_week,
                    Rental.created_at < end_week
                ).count()
                
                stats_data.append({
                    'period': f'Tuần {start_week.strftime("%d/%m")} - {(end_week - timedelta(days=1)).strftime("%d/%m")}',
                    'deposit': deposit,
                    'rental': rental,
                    'total': deposit + rental,
                    'count': count
                })
                dates.append(f'T{i+1}')
                deposit_data.append(deposit)
                rental_data.append(rental)
        
        elif stat_type == 'monthly':
            # 6 tháng gần nhất
            for i in range(5, -1, -1):
                month = now.month - i
                year = now.year
                while month <= 0:
                    month += 12
                    year -= 1
                
                start_month = datetime(year, month, 1)
                if month == 12:
                    end_month = datetime(year + 1, 1, 1)
                else:
                    end_month = datetime(year, month + 1, 1)
                
                deposit = sum(t.amount for t in Transaction.query.filter(
                    Transaction.type == 'deposit',
                    Transaction.status == 'success',
                    Transaction.created_at >= start_month,
                    Transaction.created_at < end_month
                ).all())
                
                rental = sum(r.price_charged for r in Rental.query.filter(
                    Rental.status == 'success',
                    Rental.created_at >= start_month,
                    Rental.created_at < end_month
                ).all())
                
                count = Transaction.query.filter(
                    Transaction.created_at >= start_month,
                    Transaction.created_at < end_month
                ).count() + Rental.query.filter(
                    Rental.created_at >= start_month,
                    Rental.created_at < end_month
                ).count()
                
                stats_data.append({
                    'period': start_month.strftime('%m/%Y'),
                    'deposit': deposit,
                    'rental': rental,
                    'total': deposit + rental,
                    'count': count
                })
                dates.append(start_month.strftime('%m/%Y'))
                deposit_data.append(deposit)
                rental_data.append(rental)
    
    # Tạo biểu đồ
    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Nạp tiền',
        x=dates,
        y=deposit_data,
        marker_color='#28a745'
    ))
    fig.add_trace(go.Bar(
        name='Thuê số',
        x=dates,
        y=rental_data,
        marker_color='#667eea'
    ))
    
    fig.update_layout(
        barmode='group',
        title=f'Thống kê doanh thu',
        xaxis_title='Thời gian',
        yaxis_title='Doanh thu (VNĐ)',
        template='plotly_white',
        height=500
    )
    
    stats_chart = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    full_template = BASE_TEMPLATE.replace('{% block content %}{% endblock %}', STATISTICS_TEMPLATE)
    return render_template_string(
        full_template,
        stats_data=stats_data,
        stats_chart=stats_chart,
        stat_type=stat_type,
        now=now
    )

@app.route('/add_money', methods=['POST'])
def add_money():
    """API cộng tiền thủ công"""
    user_id = request.form.get('user_id', type=int)
    amount = request.form.get('amount', type=int)
    reason = request.form.get('reason', 'Cộng tiền thủ công')
    
    if not user_id or not amount or amount < 1000:
        flash('Vui lòng nhập đủ thông tin và số tiền phải >= 1000đ', 'danger')
        return redirect(request.referrer or url_for('manual'))
    
    with app.app_context():
        user = User.query.filter_by(user_id=user_id).first()
        if not user:
            flash(f'Không tìm thấy user có ID {user_id}', 'danger')
            return redirect(request.referrer or url_for('manual'))
        
        # Tạo transaction
        transaction = Transaction(
            user_id=user.id,
            amount=amount,
            type='deposit',
            status='success',
            transaction_code=f"MANUAL_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            description=reason,
            created_at=datetime.now()
        )
        
        # Cộng tiền
        old_balance = user.balance
        user.balance += amount
        
        db.session.add(transaction)
        db.session.commit()
        
        logger.info(f"✅ ĐÃ CỘNG {amount}đ THỦ CÔNG CHO USER {user_id} (từ {old_balance}đ lên {user.balance}đ)")
        flash(f'Đã cộng {amount:,}đ thành công cho user {user_id}', 'success')
    
    return redirect(request.referrer or url_for('manual'))

@app.route('/toggle_ban', methods=['POST'])
def toggle_ban():
    """API khóa/mở khóa user"""
    data = request.get_json()
    user_id = data.get('user_id')
    
    with app.app_context():
        user = User.query.filter_by(user_id=user_id).first()
        if user:
            user.is_banned = not user.is_banned
            db.session.commit()
            return jsonify({'success': True, 'banned': user.is_banned})
    
    return jsonify({'success': False, 'message': 'Không tìm thấy user'})

@app.route('/export_users')
def export_users():
    """Xuất danh sách user ra CSV"""
    import csv
    from flask import Response
    import io
    
    with app.app_context():
        users = User.query.all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['ID', 'User ID', 'Username', 'Số dư', 'Đã thuê', 'Tổng chi', 'Ngày tạo', 'Bị khóa'])
        
        for u in users:
            writer.writerow([
                u.id,
                u.user_id,
                u.username or '',
                u.balance,
                u.total_rentals,
                u.total_spent,
                u.created_at.strftime('%Y-%m-%d %H:%M'),
                'Có' if u.is_banned else 'Không'
            ])
        
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=users.csv'}
        )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
