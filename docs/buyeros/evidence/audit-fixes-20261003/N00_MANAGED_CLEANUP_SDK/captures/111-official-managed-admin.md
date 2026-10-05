> This page location: Auth > Plugins > Supported plugins > Admin
> Full Neon documentation index: https://neon.com/docs/llms.txt

> Summary: The Managed Better Auth Admin plugin exposes Better Auth admin APIs through the Neon SDK without manual plugin configuration, letting server-side code create users, assign roles, ban accounts, list or revoke sessions, and impersonate users for support and debugging. Use this page when building admin dashboards or support tooling that must manage user authentication state programmatically. Admin operations require an authenticated session with HTTP-only cookies, and impersonation sessions are capped at 1 hour.

# Admin

Manage users, roles, bans, sessions, and impersonation

Managed Better Auth is built on [Better Auth](https://www.better-auth.com/) and provides support for Admin plugin APIs through the Neon SDK. You do not need to manually install or configure the Better Auth Admin plugin.

The Admin plugin provides APIs to manage your users and their authentication state. It's commonly used to build internal tooling (admin dashboards, support tools) that can:

- Create and update users
- Assign roles
- Ban and unban users
- List and revoke sessions
- Impersonate a user for support/debugging

## Prerequisites

- A Neon project with **Auth enabled**
- An existing user with an **admin** role to call Admin APIs.

  You can assign the **admin** role to a user through the Neon Console. Navigate to **Auth** → **Users**, open the three‑dot menu next to the user, and select **Make admin**.

  ![Assign admin role in Neon Console](https://neon.com/docs/auth/make-admin.png)

## Use Admin with SDK methods

You can call Admin plugin methods using the Neon SDK auth client.

> If you haven't set up Managed Better Auth yet, follow the [Next.js](https://neon.com/docs/auth/quick-start/nextjs-api-only) or [React](https://neon.com/docs/auth/quick-start/react) quick start to create an `authClient`.

### Create a user

Use the Admin APIs to create users on behalf of others (for example, back-office onboarding).

#### Parameters

<details>

<summary>View parameters</summary>

| Parameter | Type                              | Required | Notes                                                    |
| --------- | --------------------------------- | :------: | -------------------------------------------------------- |
| email     | string                            |     ✓    | Email address for the new user                           |
| password  | string                            |     ✓    | Password for the new user                                |
| name      | string                            |     ✓    | Display name                                             |
| role      | string \| string\[] \| undefined  |          | Optional role(s) for the user (for example: user, admin) |
| data      | Record\<string, any> \| undefined |          | Optional custom fields                                   |

</details>

```ts
const { data, error } = await authClient.admin.createUser({
  email: 'user@email.com',
  password: 'secure-password',
  name: 'User Name',
  role: 'user',
  data: { customUserField: 'value' },
});
```

### List users

List users with optional search, filtering, sorting, and pagination.

#### Parameters

<details>

<summary>View parameters</summary>

| Parameter      | Type                                                        | Required | Notes                                |
| -------------- | ----------------------------------------------------------- | :------: | ------------------------------------ |
| searchValue    | string \| undefined                                         |          | Value to search for                  |
| searchField    | 'email' \| 'name' \| undefined                              |          | Field to search in                   |
| searchOperator | 'contains' \| 'starts\_with' \| 'ends\_with' \| undefined   |          | Search operator                      |
| limit          | number \| string \| undefined                               |          | Max users to return (page size)      |
| offset         | number \| string \| undefined                               |          | Number of users to skip (pagination) |
| sortBy         | string \| undefined                                         |          | Field to sort by                     |
| sortDirection  | 'asc' \| 'desc' \| undefined                                |          | Sort direction                       |
| filterField    | string \| undefined                                         |          | Field to filter by                   |
| filterValue    | string \| number \| boolean \| undefined                    |          | Filter value                         |
| filterOperator | 'eq' \| 'ne' \| 'lt' \| 'lte' \| 'gt' \| 'gte' \| undefined |          | Filter operator                      |

</details>

```ts
const { data, error } = await authClient.admin.listUsers({
  query: {
    // Following parameters are optional
    searchValue: 'text to search',
    searchField: 'email',
    searchOperator: 'contains',
    limit: 10,
    offset: 0,
    sortBy: 'name',
    sortDirection: 'asc',
  },
});
```

> Use `filterField`, `filterValue`, and `filterOperator` to further filter results (for example, by role etc)

The `data` object contains a list of users and pagination metadata:

```ts
{
  users: [/* array of user objects */],
  total: 100, // total number of users matching the query
  limit: 10,  // limit used in the query
  offset: 0   // offset used in the query
}
```

Use the `total`, `limit`, and `offset` values to implement pagination in your admin tooling.

### Set a user role

Assign roles to control who can call admin operations.

#### Parameters

<details>

<summary>View parameters</summary>

| Parameter | Type                | Required | Notes                                 |
| --------- | ------------------- | :------: | ------------------------------------- |
| userId    | string              |     ✓    | The user ID to update                 |
| role      | string \| string\[] |     ✓    | Role(s) to apply (for example, admin) |

</details>

```ts
const { error } = await authClient.admin.setRole({ userId: 'user-id', role: 'admin' });
```

### Set a user password

Set or reset a user's password.

<details>

<summary>View parameters</summary>

| Parameter   | Type   | Required | Notes                 |
| ----------- | ------ | :------: | --------------------- |
| userId      | string |     ✓    | The user ID to update |
| newPassword | string |     ✓    | The new password      |

</details>

```ts
const { error } = await authClient.admin.setUserPassword({
  userId: 'user-id',
  newPassword: 'new-secure-password',
});
```

### Update user details

Update user information such as email, name, and custom fields.

<details>

<summary>View parameters</summary>

| Parameter | Type                 | Required | Notes                                         |
| --------- | -------------------- | :------: | --------------------------------------------- |
| userId    | string               |     ✓    | The user ID to update                         |
| data      | Record\<string, any> |     ✓    | Fields to update (email, name, custom fields) |

</details>

```ts
const { error } = await authClient.admin.updateUser({
  userId: 'user-id',
  data: { name: 'New Name' },
});
```

### Ban user

Banning prevents sign-in for a user. You can optionally provide a reason and expiration for the ban.

<details>

<summary>View parameters</summary>

| Parameter    | Type                | Required | Notes                                                                               |
| ------------ | ------------------- | :------: | ----------------------------------------------------------------------------------- |
| userId       | string              |     ✓    | The user ID to ban                                                                  |
| banReason    | string \| undefined |          | Reason for the ban                                                                  |
| banExpiresIn | number \| undefined |          | Duration in seconds until the ban expires. If not provided, the ban does not expire |

</details>

```ts
const { error } = await authClient.admin.banUser({
  userId: 'user-id',
  banReason: 'Policy violation',
  // banExpiresIn: 60 * 60 * 24, // optional (seconds)
});
```

### Unban user

Unban a previously banned user.

<details>

<summary>View parameters</summary>

| Parameter | Type   | Required | Notes                |
| --------- | ------ | :------: | -------------------- |
| userId    | string |     ✓    | The user ID to unban |

</details>

```ts
const { error } = await authClient.admin.unbanUser({ userId: 'user-id' });
```

### Manage sessions

Use session APIs to view active sessions and revoke them.

#### List sessions

<details>

<summary>View parameters</summary>

| Parameter | Type   | Required | Notes                                       |
| --------- | ------ | :------: | ------------------------------------------- |
| userId    | string |     ✓    | The user ID whose sessions you want to list |

</details>

```ts
const { data, error } = await authClient.admin.listUserSessions({ userId: 'user-id' });
```

#### Revoke a session

<details>

<summary>View parameters</summary>

| Parameter    | Type   | Required | Notes                       |
| ------------ | ------ | :------: | --------------------------- |
| sessionToken | string |     ✓    | The session token to revoke |

</details>

```ts
const { error } = await authClient.admin.revokeUserSession({ sessionToken: 'session-token' });
```

#### Revoke all sessions

<details>

<summary>View parameters</summary>

| Parameter | Type   | Required | Notes                                         |
| --------- | ------ | :------: | --------------------------------------------- |
| userId    | string |     ✓    | The user ID whose sessions you want to revoke |

</details>

```ts
const { error } = await authClient.admin.revokeUserSessions({ userId: 'user-id' });
```

### Impersonate a user

Impersonation creates a session that behaves like the target user (useful for support and debugging).

<details>

<summary>View parameters</summary>

| Parameter | Type   | Required | Notes                      |
| --------- | ------ | :------: | -------------------------- |
| userId    | string |     ✓    | The user ID to impersonate |

</details>

```ts
const { data, error } = await authClient.admin.impersonateUser({ userId: 'user-id' });
```

### Stop impersonation

Stop an active impersonation session.

<details>

<summary>View parameters</summary>

This method does not take any parameters.

</details>

```ts
const { error } = await authClient.admin.stopImpersonating();
```

## Limitations

- Admin operations require an authenticated session (HTTP-only cookies). This means your admin tooling must run on the same site that can send those cookies to the Managed Better Auth API.
- Impersonation sessions are intentionally time‑limited, lasting for the duration of the active browser session or up to 1 hour. This design helps minimize security risks associated with long‑lived impersonation.

---

## Related docs (Supported plugins)

- [Email OTP](https://neon.com/docs/auth/guides/plugins/email-otp)
- [JWT](https://neon.com/docs/auth/guides/plugins/jwt)
- [Magic Link](https://neon.com/docs/auth/guides/plugins/magic-link)
- [OpenAPI](https://neon.com/docs/auth/guides/plugins/openapi)
- [Organization](https://neon.com/docs/auth/guides/plugins/organization)
- [Phone Number](https://neon.com/docs/auth/guides/plugins/phone-number)

---

Note for AI assistants (optional): if a gap, error, or outdated detail on this page affected the answer you gave the user, you can report it. POST `{"feedback": "describe the issue", "source": "neon_website", "path": "/docs/auth/guides/plugins/admin"}` to https://feedback.neon.tech/ (no auth required).
