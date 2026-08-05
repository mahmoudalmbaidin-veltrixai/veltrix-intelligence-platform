# Authenticated API Contract Report

The current OpenAPI surface contains 192 paths and 247 operations. `api-operation-coverage.json` classifies all 247/247 by authentication scope, action, resource binding, personas, security dimensions, and mapped test IDs.

The operation-level framework derives cases from the real application OpenAPI document and runs against PostgreSQL with real authenticated personas. It validates declared response shapes/statuses and relevant invalid UUID, missing resource, unauthorized, forbidden, cross-tenant, suspended-user, invalid/extra/wrong-type/empty payload, pagination/filter/sort, tenant-header manipulation, UUID enumeration, role ceiling, ACL/explicit deny, expired access, secret non-disclosure, signed/export authorization dimensions.

Three contract integration tests passed as part of each 64-test integration run. They use the production app factory and real database; mocks do not replace domain authorization or persistence. Disabled/placeholder operations remain classified and inaccessible rather than counted as authenticated happy paths.

Security correction discovered during certification: collection endpoints previously omitted resource-level deny filtering for users with broad workspace roles. Connection, dataset, semantic, pipeline, and dashboard collections now subtract active explicit denies before returning rows; direct access and list omission are covered by PostgreSQL integration and browser governance tests.
