# Project-Mitori
A microservice-based stock brokerage platform and order book analytics engine

### What is this?
Project Mitori is a custom-built stock trading platform I am developing from scratch. The goal is to learn how real financial systems work under the hood. 

Right now, I am building the "Bank Vault"—a secure backend ledger using **Django** and **PostgreSQL** to handle user accounts, portfolios, and transaction history. Later, I will add a high-speed matching engine (FastAPI) and a web dashboard (Next.js).

This README serves as my daily development log.

---

### What I've Built So Far

**1. Secure Authentication**
* Ripped out Django's default username system.
* Built a custom User model (`AbstractBaseUser`) that uses Email and Password as the primary login, matching modern app standards.
* Added KYC (Know Your Customer) document tracking directly into the user profile.

**2. The Financial Ledger Architecture**
* Created an isolated PostgreSQL database to prevent data bleeding.
* Built the `Portfolio` model (1-to-1 tied to the user) to track raw cash balances.
* Built the `Position` model to track exactly what assets a user holds.
* Built the `LedgerTransaction` model to log every single Deposit, Withdrawal, Buy, and Sell with strict timestamping.
* Enforced `DecimalField` (4 decimal places) across the board to prevent floating-point math errors with money.

* ...