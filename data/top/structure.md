# Data structure
## List
- title: string
- category: string enum (music, sports, games)
- subcategory: optional string (sports: basketball, soccer, hockey)
- user_id (optional)
- predefined: boolean, default false
- size: number, default 50
- time_period: string, default "all"
- parent_list_id: optional id (inherited list from)

## User
- external_id: optional string
- username: optional string
- passowrd: optional string

## Items
- name: string
- category: string
- subcategory: string optional
- accolades: string optional
- reference_url: string optional

## Items vs List
- parent_list_id: optional id
- list_id: id
- item_id: id
- ranking: number 