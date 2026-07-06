# Database operations (Supabase / free tier)

Operational runbook for the hardening applied in the `a1b2c3d4e5f6` → `c3d4e5f6a7b8`
migrations. Most items below are **one-time dashboard/SQL actions** that live outside the
codebase on purpose (role passwords, extension enablement, CI secrets).

## Connection roles (least privilege)

- **Runtime** (`DATABASE_URL`): the `cutcarbon_app` role via the **transaction pooler**
  (`:6543`). Created by migration `b2c3d4e5f6a7` with only `SELECT/INSERT/UPDATE/DELETE`
  on the app tables and a permissive RLS policy — it cannot run DDL, manage roles, or read
  the `auth` schema. **Set its password once** (Supabase → SQL editor):

  ```sql
  alter role cutcarbon_app with password 'a-strong-password';
  ```
  Then set `DATABASE_URL=postgresql+asyncpg://cutcarbon_app.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres`.

- **Migrations** (`MIGRATION_DATABASE_URL`): the elevated `postgres` role on the direct/
  session connection (`:5432`). Alembic needs DDL + ownership.

> Rotate the `postgres` DB password and the `service_role` key (they were exposed during
> setup): Supabase → Database → **Reset database password**, and Settings → API → roll the
> keys. Then update `MIGRATION_DATABASE_URL`.

## RLS / Data-API posture

Migration `a1b2c3d4e5f6` enables RLS on every app table and revokes all `anon`/
`authenticated` grants (plus `ALTER DEFAULT PRIVILEGES` so future tables stay closed). The
app never uses PostgREST, so the Data API surface is intentionally shut. Verify:

```sql
-- all app tables must show rowsecurity = true
select relname, relrowsecurity from pg_class
 where relnamespace = 'public'::regnamespace and relkind = 'r';
-- must return no rows
select grantee, table_name from information_schema.role_table_grants
 where table_schema = 'public' and grantee in ('anon','authenticated');
```
An anon-key `GET https://<ref>.supabase.co/rest/v1/scenarios` should return `200 []`.

## Keep-alive + retention (pg_cron)

Free projects **auto-pause after ~7 days idle** and are capped at **500 MB**. Enable
`pg_cron` (Dashboard → Database → Extensions), then in the SQL editor:

```sql
-- Keep the project warm (a real DB query — pinging the app's /health does NOT count,
-- it never touches the DB).
select cron.schedule('keepalive', '0 6 */5 * *', $$select 1$$);

-- Prune write-only audit tables to stay under the size cap.
select cron.schedule('prune-agent-runs', '0 3 * * *',
  $$delete from public.agent_runs      where fetched_at  < now() - interval '90 days'$$);
select cron.schedule('prune-emission-factors', '15 3 * * *',
  $$delete from public.emission_factors where last_updated < now() - interval '180 days'$$);
```

## Backups & restore

Free tier has **no automated backups / no PITR**. `.github/workflows/db-backup.yml` takes a
daily `pg_dump` (add repo secret `BACKUP_DATABASE_URL`, a libpq `postgresql://postgres:…`
URL). To restore a dump into a scratch/target database:

```bash
gunzip -c cutcarbon_<ts>.sql.gz | psql "postgresql://postgres:<pw>@db.<ref>.supabase.co:5432/postgres"
```

Test restores periodically into a throwaway schema/project so the dumps are known-good.

## Auth-user lifecycle

`public.users.id` is FK'd to `auth.users(id) ON DELETE CASCADE` (migration
`c3d4e5f6a7b8`), and all child tables cascade from `public.users`. Deleting a user in
Supabase Auth (Dashboard → Authentication → Users, or the Admin API) therefore removes
their profile and all owned scenarios/chat/reports/offsets automatically (GDPR erasure).
Profiles are still JIT-provisioned on first authenticated request (`app/routers/auth.py`).
