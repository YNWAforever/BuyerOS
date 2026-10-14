# Import buyer candidates from Excel or CSV

Open a live project's buyer results and choose **Import Excel / CSV**. Operators and workspace administrators can preview and confirm files. The preview belongs to the person who uploaded it.

1. Select an `.xlsx` workbook or a UTF-8 `.csv` file.
2. Review the rows, source dates, duplicates and errors in the preview.
3. Fix any invalid rows in the source file and preview the corrected file again. Every invalid row must be resolved before confirmation.
4. Confirm the exact preview. All new candidates and their source records are saved in one transaction. Existing project buyers and repeated rows are skipped.

An import creates **unreviewed research candidates**. It does not accept buyers, verify legal entities, verify contact details, perform paid research, or send messages. Email addresses and commercial hypotheses remain source text only.

## File layout

The only required column is a company name. Common accepted headings are:

| Value | Accepted headings |
| --- | --- |
| Company name | `Company`, `Company name`, `Company / trading name`, `Buyer name`, `Name`, `公司名稱` |
| Website or domain | `Website`, `Website URL`, `Domain`, `公司網站` |
| Source date | `Source date`, `Checked on`, `Checked date`, `As of`, `資料日期` |
| Evidence link | `Source URL`, `Evidence source URL`, `Evidence URL`, `來源網址` |
| Contact source link | `Contact source URL` |
| Original row reference | `Source row`, `來源行` |

Heading matching ignores case, spaces and punctuation. Use one heading per value: for example, a file containing both `Company` and `Company name` needs one of them renamed or removed so the company-name field is unambiguous. Other columns, such as wave, buyer type, qualification gaps and notes, are preserved as source fields.

Use dates such as `2026-09-18`. Excel date serials in the source-date column are supported. Dates remain the source's stated date; uploading a file does not make its research current.

For workbooks, the importer prefers the **Buyer List** sheet. Otherwise it selects a sheet with a recognized company-name heading in its first 20 nonempty rows. This supports a title and introductory rows above the table. Only the selected buyer table is imported.

A generic CSV example:

```csv
Company,Website,Source URL,Source date,Wave,Public contact route,Qualification gap
Example Foods,https://foods.example,https://foods.example/about,2026-09-18,1,procurement@foods.example,Confirm purchasing responsibilities
Example Distribution,https://distribution.example,https://distribution.example/catalogue,2026-09-18,2,Website enquiry form,Confirm product requirements
```

The `.example` domains and addresses above are illustrative. They are not outreach destinations.

## Limits and validation

- Maximum file size: **5 MiB**.
- Maximum buyer rows: **500**; maximum columns: **64**.
- Maximum cell value: **10,000 characters**; maximum company name: **400 characters**.
- Maximum expanded source text: **2,000,000 characters** across parsed rows; maximum serialized source data: **8 MiB**, including repeated header names.
- CSV must be UTF-8; a UTF-8 byte-order mark is accepted. Every data row must have the same number of columns as the header.
- XLSX processing is offline and bounded to **16 MiB** of expanded workbook data. Legacy `.xls`, macros, external workbook links, XML entities and formula cells are not supported. Replace formulas with the source values before uploading.
- Website and source-link fields accept public HTTP or HTTPS URLs. Script URLs, file URLs, embedded credentials, local addresses and IP-address URLs are rejected. Links are not fetched during import.

The original fields are kept with the source row, source date, file name and file SHA-256. Open a buyer's import-source panel to inspect them. The importer does not infer a legal registration or contact permission from a spreadsheet cell.

## Duplicate and identity handling

Within the current project, a matching normalized domain or normalized company name is shown as a duplicate. Repeated identities within the uploaded file are also duplicates. Existing buyers, their reviews and their evidence remain intact.

A similar company elsewhere in the workspace is flagged for **manual identity mapping**. A name or domain is an identity hint, so importing it does not automatically associate the candidate with another project's company record or evidence.

Conflicting hints also require manual mapping. For example, if a row's name matches one company but its domain matches another, or several companies share that domain, the importer flags the ambiguity instead of choosing a company.

If duplicates change after the preview, confirmation stops and requires a fresh preview. Previews expire after two hours. A file containing only duplicates has no new rows to import.

## Recovering an interrupted confirmation

If the response is interrupted, use the import result lookup or retry the original confirmation. The server returns the original committed result for the same import instead of creating another batch. The page retains the import ID in its URL so its result can be checked after a refresh. A completed result reports the created buyer IDs and the number of skipped duplicates.

For API clients, the flow is:

- `POST /v1/workspaces/{workspace_id}/projects/{project_id}/buyer-imports/preview` — multipart `file`, plus `Idempotency-Key`.
- `POST /v1/workspaces/{workspace_id}/projects/{project_id}/buyer-imports/{import_id}/confirm` — `{"preview_digest":"sha256:…","confirmation":true}`, plus the original confirmation's `Idempotency-Key`.
- `GET /v1/workspaces/{workspace_id}/projects/{project_id}/buyer-imports/{import_id}` — read the staged preview or committed result.
- `GET /v1/workspaces/{workspace_id}/buyers/{buyer_id}/import-source` — read source provenance; returns `data: null` for an authorized buyer that was not imported.

Reuse the original confirmation key and payload when retrying. A changed payload with the same key is rejected. All endpoints require the existing authenticated workspace access; file contents cannot choose a different workspace, project or actor.
