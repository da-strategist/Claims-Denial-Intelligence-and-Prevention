# Pilot server on AWS

One small server in us-east-1 that runs the API and the app for pilot organisations, with real
claims only. The demo stays on Fly (API) and Vercel (website and app); nothing here touches it.

```
browser ──HTTPS──> Elastic IP ──> EC2 t4g.micro (Amazon Linux 2023)
                                   ├─ Caddy  :443/:80  certificate, security headers, the built app
                                   └─ API    127.0.0.1:8000  (systemd, its own account)
                                        ├─ /srv/vericlaim/data   encrypted files, on an encrypted disk
                                        └─ KMS key               wraps each organisation's data key
```

No SSH, no load balancer, no database service, no NAT gateway. The server is reached with
Session Manager, settings come from the install script, and the only secret (the Anthropic key,
optional) sits in Parameter Store.

## Before you start

1. **The AWS Business Associate Addendum is accepted** (AWS Artifact → Agreements →
   Organization agreements, from the management account). Don't create anything before this:
   the pilot carries patient information.
2. Root sign-in has MFA turned on.
3. The account is on the paid plan (the free plan's credits still apply until they run out).

## 1. Build the bundle (your computer)

```bash
claim_validation_tool/deploy/aws/bundle.sh
```

This writes `dist/vericlaim-pilot-<version>.tgz`. It holds the API (without tests), the built
app, the shared code sets and these scripts. It holds no organisations, accounts or claims,
and the script refuses to build if a `.env`, key or data file gets in.

## 2. Open CloudShell in us-east-1

In the console, switch the region (top right) to **US East (N. Virginia)**, then open
CloudShell (the `>_` icon). Upload the bundle with **Actions → Upload file**, then:

```bash
tar xzf vericlaim-pilot-*.tgz && cd vericlaim-pilot
cp aws/config.env.example aws/config.env
nano aws/config.env          # set BUDGET_EMAIL; the rest can stay
```

## 3. Create the resources (once)

```bash
./aws/provision.sh
```

It's safe to run again: it only creates what isn't there. It prints the server's address,
`https://<ip-with-dashes>.sslip.io`. sslip.io is a free name that points at the IP, so Caddy
can get a real certificate without a domain.

## 4. Install the app

```bash
./aws/deploy.sh ../vericlaim-pilot-*.tgz
```

The first run takes about 5 minutes (Python, the app's packages, Caddy). It ends with
`Live at https://…/app`. For each new version, build a new bundle and run `deploy.sh` with it
(only steps 1, 2 and 4); the data stays where it is, and the last 3 versions are kept.

## 5. Create the platform account

In the console: **EC2 → Instances → vericlaim-pilot → Connect → Session Manager → Connect**.
Then:

```bash
sudo vericlaim-admin users add superadmin --name "Your Name" --role platform
```

It asks for the password itself; type it there, not in chat or a file. Then sign in at
`https://…/app`, and add each pilot organisation with its first admin from the Platform page. Record its
signed BAA there too: in production, an organisation without one can't sign in.

Other commands: `sudo vericlaim-admin users list`, `sudo vericlaim-admin orgs list`,
`sudo vericlaim-admin orgs key-status`.

## 6. The AI assistant (optional)

Without a key the assistant runs on its rules only. To use Claude, in CloudShell:

```bash
aws ssm put-parameter --region us-east-1 --name /vericlaim-pilot/anthropic-api-key \
  --type SecureString --value "$(read -rsp 'Key: ' k; echo "$k")"
```

Then restart the API from Session Manager: `sudo systemctl restart vericlaim-api`. Before the
assistant sees claim details, the Anthropic BAA (or zero data retention) must be in place.

## Later: your own domain

1. Point an `A` record (e.g. `app.example.com`) at the Elastic IP.
2. In CloudShell, set `DOMAIN=app.example.com` in `aws/config.env`.
3. Run `./aws/deploy.sh` with the current bundle. Caddy gets the new certificate.

Email (password resets, invitations) also waits for the domain: SES needs one to send from.

## What it costs

| Item | Per month |
|---|---|
| EC2 t4g.micro (2 vCPU burst, 1 GB + 2 GB swap) | $6.10 |
| 20 GB encrypted gp3 disk | $1.60 |
| Elastic IP (public IPv4) | $3.65 |
| KMS key | $1.00 |
| Daily snapshots, 7 kept (only changed blocks) | ~$0.50 |
| S3 release bundles (deleted after 30 days) | ~$0.01 |
| Session Manager, Parameter Store (standard), budget alert, CloudShell, sslip.io | free |
| **Total** | **~$13** |

Data sent out of AWS: the first 100 GB a month are free, far more than a pilot uses. The
budget alert emails `BUDGET_EMAIL` at 50% and 100% of `BUDGET_USD` (default $20), and when
the month is forecast to go over.

## Checks

```bash
# From Session Manager on the server
systemctl status vericlaim-api caddy
journalctl -u vericlaim-api -n 50
curl -s 127.0.0.1:8000/api/health
```

## Backups and restore

Data Lifecycle Manager snapshots the disk every day at 07:00 UTC and keeps 7. To restore:
**EC2 → Snapshots**, pick one, **Create volume** in the same zone, stop the instance, swap the
root volume (**Replace root volume** on the instance), start it. The data stays encrypted with
the same KMS key, so keep the key: scheduling its deletion makes every backup unreadable.

## Taking it down

The instance has termination protection and its disk is kept on termination, so nothing
disappears by accident. To remove everything, in this order: export what you need, turn off
termination protection and terminate the instance, delete the volume and the snapshots
(and the DLM policy), release the Elastic IP, empty and delete the bucket, delete the role,
the security group and the budget, and last schedule the KMS key for deletion (7 to 30 days).
