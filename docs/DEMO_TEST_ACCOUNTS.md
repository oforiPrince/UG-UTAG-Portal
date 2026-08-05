# Dashboard demo accounts

The demo-data command creates active, email-verified accounts for each built-in
role and fictional profiles for every canonical executive position. It is
blocked outside development and test environments.

Set a strong shared password without saving it in the repository, then run:

```bash
DEMO_DATA_PASSWORD='choose-a-strong-test-password' make seed-demo
```

Running the command again is safe. It restores the named demo accounts, their
roles, known password, organization placement and current executive
appointments. It does not change non-demo users.

## Role acceptance accounts

| Experience | Email |
| --- | --- |
| Member | `demo.member@utag.com` |
| Executive | `demo.executive@utag.com` |
| Editor | `demo.editor@utag.com` |
| Publisher | `demo.publisher@utag.com` |
| Secretary | `demo.secretary@utag.com` |
| Administrator | `demo.administrator@utag.com` |

All accounts use the password supplied in `DEMO_DATA_PASSWORD`.

## Additional executive accounts

The seed also creates active, public appointments and login-ready Executive
accounts for Vice-President, Assistant Secretary, Treasurer, Assistant
Treasurer, Organiser, Women's Executive Officer, Past President, National
President, and the CBAS, CHS, COE and COH representatives.

Their email addresses follow the visible position, for example
`demo.vice-president@utag.com`, `demo.treasurer@utag.com` and
`demo.cbas-rep@utag.com`.

These records are explicitly fictional and use the `DEMO-` staff-ID prefix.
They must never be treated as migrated or production membership data.
