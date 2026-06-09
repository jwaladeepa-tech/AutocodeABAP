# ABAP Deployment Setup Guide - S/4HANA 2022

## Prerequisites

### 1. SAP System Requirements
- **SAP S/4HANA 2022** on-premise
- **ADT (ABAP Development Tools)** enabled (default: enabled)
- **HTTP/HTTPS** access to the system
- RFC user with deployment permissions

### 2. SAP User Account
Create a dedicated RFC user in SAP with the following roles:
- `S_DEVELOP` - Development permission
- `S_ADMI_FCD` - Admin function code permission
- Package permission for your development package (e.g., `ZDEV_PACKAGE`)

**Steps to create user in SAP:**
1. Transaction: `SU01` (User Maintenance)
2. Create new user with type: `System`
3. Assign role: `SAP_J2EE_DEVELOPER`
4. Assign package permissions: `ZDEV_PACKAGE`

---

## GitHub Secrets Configuration

Add the following secrets to your GitHub repository:

1. Go to **Settings → Secrets and variables → Actions**
2. Add each secret:

| Secret Name | Description | Example |
|------------|-------------|---------|
| `SAP_HOST` | SAP system hostname | `sap-prod.company.com` |
| `SAP_PORT` | SAP HTTP port | `8000` |
| `SAP_CLIENT` | SAP client number | `100` |
| `SAP_USER` | RFC user (non-interactive) | `DEPLOY_USER` |
| `SAP_PASSWORD` | User password | `****` |

**Example Configuration:**
```
SAP_HOST=192.168.1.100
SAP_PORT=8000
SAP_CLIENT=100
SAP_USER=RFC_DEPLOY
SAP_PASSWORD=YourSecurePassword123
```

---

## Directory Structure

Your repository should follow this structure:

```
AutocodeABAP/
├── .github/
│   └── workflows/
│       ├── abap-ci.yml          # Linting workflow
│       └── abap-deploy.yml      # Deployment workflow
├── scripts/
│   └── deploy_adt.py            # ADT deployment script
├── src/
│   ├── programs/
│   │   └── z_test_program.abap
│   ├── classes/
│   │   ├── z_test_class.clas
│   │   └── z_test_class.clas.abap
│   └── reports/
│       └── z_report.prog
├── abaplint.json
└── README.md
```

---

## How It Works

### Deployment Workflow (`.github/workflows/abap-deploy.yml`)

**Triggers:**
- ✅ Automatic on push to `main` branch (if files in `src/` change)
- ✅ Manual via `workflow_dispatch` with custom package parameter

**Stages:**
1. **Lint** - Run abaplint to validate ABAP code quality
2. **Deploy** - Upload ABAP objects to S/4HANA via ADT API
3. **Activate** - Activate objects in SAP system
4. **Report** - Generate deployment report

### Deployment Script (`scripts/deploy_adt.py`)

The script:
1. ✅ Authenticates to SAP using ADT REST API
2. ✅ Finds all ABAP files in `src/` directory
3. ✅ Deploys each object to the specified package
4. ✅ Activates all deployed objects
5. ✅ Generates deployment report with status

---

## Supported ABAP File Types

| File Extension | ABAP Object Type | Example |
|---|---|---|
| `.abap` | Source code | Program source |
| `.prog` | Program (Report) | ABAP report |
| `.clas` | Class definition | OOP class |
| `.intf` | Interface | OOP interface |
| `.fugr` | Function Group | RFC function group |
| `.ddls` | Data Definition Language | CDS view |
| `.tabl` | Table | Database table |

---

## Testing the Deployment

### 1. Manual Trigger
```
GitHub → Actions → Deploy ABAP to S/4HANA 2022 → Run workflow
```

### 2. Create Test ABAP File
Create `src/programs/z_hello_world.prog`:
```abap
REPORT z_hello_world.
WRITE 'Hello World from GitHub Actions!'.
```

### 3. Push to Main
```bash
git add .
git commit -m "Add test ABAP program"
git push origin main
```

### 4. Monitor Deployment
- GitHub Actions will automatically trigger
- Check workflow logs for status
- Review `deployment-report.json` artifact

---

## Troubleshooting

### Connection Issues
```
Error: Cannot connect to SAP system
```
**Solution:**
- Verify `SAP_HOST` and `SAP_PORT` are correct
- Check network connectivity: `ping <SAP_HOST>`
- Ensure HTTP/HTTPS is enabled on SAP system
- Check firewall rules

### Authentication Failed
```
Error: Authentication failed - Invalid credentials
```
**Solution:**
- Verify `SAP_USER` and `SAP_PASSWORD` are correct
- Ensure user exists in SAP and is not locked
- Check user permissions and roles
- Verify client number (`SAP_CLIENT`)

### No Files Found
```
Warning: No ABAP files found to deploy
```
**Solution:**
- Create ABAP files in `src/` directory
- Use supported file extensions (`.prog`, `.clas`, `.abap`, etc.)
- Check file paths and naming conventions

### Activation Failed
```
Error: Activation error
```
**Solution:**
- Check object syntax (run abaplint locally)
- Verify package exists in SAP
- Check object name conventions (start with `Z` or `Y`)
- Review deployment report for details

---

## Security Best Practices

1. **Never commit credentials**
   - Use GitHub Secrets for all sensitive data
   - Keep `deploy_adt.py` in version control (no secrets)

2. **Use dedicated RFC user**
   - Create separate deployment user (not admin)
   - Limit permissions to required package only
   - Use strong password with special characters

3. **Enable HTTPS** (if available in your SAP system)
   - Modify `deploy_adt.py` to use `https://` URLs
   - Import SSL certificates if needed

4. **Audit deployments**
   - Review deployment reports regularly
   - Monitor workflow logs for suspicious activity
   - Set GitHub branch protection rules

---

## Advanced Configuration

### Custom Package Name
Override default package via workflow input:
```bash
GitHub → Actions → Deploy ABAP to S/4HANA 2022 → Run workflow
Select package: ZPROD_PACKAGE
```

### Filter Deployment by Path
Modify `.github/workflows/abap-deploy.yml`:
```yaml
push:
  paths:
    - 'src/programs/**'    # Only deploy programs
    - 'src/classes/**'     # Only deploy classes
```

### Scheduled Deployments
Add schedule trigger to workflow:
```yaml
schedule:
  - cron: '0 2 * * *'     # Deploy daily at 2 AM
```

---

## Support & Monitoring

- **Deployment Logs**: GitHub Actions → Workflow Logs
- **Artifacts**: Download `deployment-report.json` for details
- **SAP Logs**: Transaction `SM37` (Job Log) and `ST22` (Dump)
- **ADT Logs**: Check ADT traces in SAP system

---

## Next Steps

1. ✅ Configure GitHub Secrets
2. ✅ Create RFC user in SAP
3. ✅ Add ABAP files to `src/` directory
4. ✅ Test deployment manually via GitHub Actions
5. ✅ Monitor first deployment and review logs
6. ✅ Enable automatic deployments on push

For questions or issues, review the deployment report and SAP system logs.
