# Historical benchmark boundary
The adjacent CF07 benchmark is copied unchanged from audited public repository a78859f.
It is historical local Win/PG16 in-process ASGI evidence, not this audit's production timing.
Its source-bound 10k-buyers/100-workspaces fixture reported sequential p95 58.603ms,
10-distinct-actors p95 258.649ms, 11 queries/request and 50,721 bytes. Consult JSON for exact source and method.
It measures buyer reads, not the workspace-list fanout exercised by E06.
No new production LCP, INP, CLS, p95, p99, contact accuracy or real-provider benchmark was run.
