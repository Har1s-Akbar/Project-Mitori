import uuid
import json
from decimal import Decimal
from django.test import TransactionTestCase
from django.conf import settings
from django.db import connection
import concurrent.futures

from core_ledger.models import Portfolio, Position, LedgerTransaction, TransactionType, Status
from django.contrib.auth import get_user_model
from core_ledger.management.commands.trade_registery import Command
from core_ledger.services import redis_positions_portfolio_service

from core_ledger.test.test_services import test_redis_client