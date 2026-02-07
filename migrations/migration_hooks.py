"""
Custom hooks for Alembic migrations.
Automatically inject triggers, seed data, and other custom SQL into generated migrations.
"""

from alembic.operations import ops


def process_revision_directives(context, revision, directives):
    """
    Hook to automatically inject custom SQL (triggers, seed data) into generated migrations.
    This runs after autogenerate but before writing the migration file to disk.

    SQL is imported from model classes to keep migration logic close to the models.
    """
    if directives[0].upgrade_ops is None:
        return

    from backend.database.tables.balance import Balance
    from backend.database.tables.transaction_type import TransactionType
    from backend.database.tables.user import User

    created_tables = set()

    for op in directives[0].upgrade_ops.ops:
        if isinstance(op, ops.CreateTableOp):
            created_tables.add(op.table_name)

    if created_tables:
        upgrade_ops = directives[0].upgrade_ops.ops
        downgrade_ops = directives[0].downgrade_ops.ops

        custom_upgrade_ops = []
        custom_downgrade_ops = []

        if User.__tablename__ in created_tables:
            user_sql = User.get_migration_trigger_sql()
            custom_upgrade_ops.append(ops.ExecuteSQLOp(user_sql["create_function"]))
            custom_upgrade_ops.append(ops.ExecuteSQLOp(user_sql["create_trigger"]))
            custom_downgrade_ops.append(ops.ExecuteSQLOp(user_sql["drop_trigger"]))
            custom_downgrade_ops.append(ops.ExecuteSQLOp(user_sql["drop_function"]))

        if TransactionType.__tablename__ in created_tables:
            seed_sql = TransactionType.get_migration_seed_sql()
            custom_upgrade_ops.append(ops.ExecuteSQLOp(seed_sql))

        if User.__tablename__ in created_tables and Balance.__tablename__ in created_tables:
            balance_sql = Balance.get_migration_trigger_sql()
            custom_upgrade_ops.append(ops.ExecuteSQLOp(balance_sql["create_function"]))
            custom_upgrade_ops.append(ops.ExecuteSQLOp(balance_sql["create_trigger"]))
            custom_downgrade_ops.append(ops.ExecuteSQLOp(balance_sql["drop_trigger"]))
            custom_downgrade_ops.append(ops.ExecuteSQLOp(balance_sql["drop_function"]))

        upgrade_ops.extend(custom_upgrade_ops)

        downgrade_ops[0:0] = custom_downgrade_ops
