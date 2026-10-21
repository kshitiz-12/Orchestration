# Email case report

Run at 2026-10-17 18:21 UTC. Pytest exit status 1.
Each case below is one automated test. Inbound is the mail the desk received. Outbound is the reply or work order it stored. Nothing here was sent to a real mailbox.
The 30-branch cases were run in a second pass after workbook import stopped issuing a Postgres-only timeout on the test database. Those 41 cases passed.

## How the replies were written, without Gemini

Gemini was not used. Nobody asked Google to write these replies.

The desk already has its own letters. It fills them in from the email and from the records:

- A mail that only says hello gets a fixed welcome: what the desk can help with, and a line asking the person to reply with what they need.
- An empty mail gets a fixed line: the mail came through empty, please send it again.
- Words in the mail pick the type. "AC not working" is air conditioning. "Fan" is electrical. "Tap" or "leak" is plumbing. "Visitors" is a visitor pass. The letter back to the person is then the fixed line: we have logged this as the case number and passed it to the team.
- The letter to the team is a fixed form: who asked, the case number, what they asked, then what the records say (warranty, AMC, how many times it was already repaired), then the words the team can reply with, such as "on it" or "done".
- Those record lines come from the database. If the warranty date is still in the future, the letter says repair it under warranty. If the repair count has hit the company's limit, the letter says replace it. If that machine is not in the records, the letter says so, and it does not invent a count or an AMC.
- In some tests the test itself types the next mail, for example the team replying "done". That typed mail is not Gemini. The desk reads it and writes the next fixed letter, such as telling the person the job is closed.

When Gemini is switched on for a real inbox, it may rephrase these letters. It still has to keep the case number, the room, and those reply words. The letters in this file are the system's own wording.

The six checks for warranty, a fan repaired 50 times, an unknown AC, a repeated cleaning, a second laptop, and expired stock are written out in plain steps under test_record_decisions.py. Those six did not send an email. They stopped at the decision. Every other mail case below is an email in, a record check, and the letter that came back.

## Summary

- Cases: 423
- Passed: 411
- Failed: 12
- Errors: 0
- Skipped: 0
- Cases that stored mail: 174

## Failed cases

- `tests/test_ai_learning.py::test_repeated_rerouting_becomes_a_one_click_rule`
- `tests/test_blueprint_controls.py::test_bare_done_asks_for_proof_and_proof_makes_closure_verified`
- `tests/test_blueprint_controls.py::test_unverified_question_goes_to_a_person_instead_of_a_guess`
- `tests/test_event_services.py::test_real_department_gets_its_list_and_done_marks_ready`
- `tests/test_event_services.py::test_service_entry_then_matching_invoice_closes_financially`
- `tests/test_event_services.py::test_service_entry_variance_and_invoice_mismatch_are_billing_exceptions`
- `tests/test_event_services.py::test_invoice_mail_quoting_the_case_is_matched`
- `tests/test_ops_resolution.py::test_team_done_with_amount_records_spend`
- `tests/test_schema_sync.py::test_old_database_gets_new_tables_and_columns_and_keeps_rows`
- `tests/test_schema_sync.py::test_new_column_with_a_simple_default_fills_existing_rows`
- `tests/test_setup_api.py::test_company_workbook_preview_and_commit`
- `tests/test_setup_api.py::test_company_ai_json_dump_import`

## Cases

### test_30_branch_matrix.py

41 cases, 0 failed.

#### test_matrix_has_thirty_branches_and_fallback_traps — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_tc01_direct_local_match_bengaluru_it — PASSED

What happened:

1. ramesh.it042@company.com sent an email. Subject: "Projector not working". They wrote: "Projector not working in 4th Floor Boardroom"
2. The desk opened ITS-2026-0001 (Projector not working in boardroom) — handed to the team and still open.
3. It checked the records. Nothing in the records blocked it, so the desk carried on.
4. It wrote to it.blr@company.com. Subject: "Work Order: Projector not working in boardroom [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Projector not working in boardroom New work …"
5. It wrote to ramesh.it042@company.com. Subject: "Re: Projector not working [ITS-2026-0001]". The message starts: "Dear Ramesh Kumar, We have logged your request and assigned it to IT - Bengaluru HQ. Request: ITS-2026-0001 Subject: Projector not working in boardroom Status:…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Projector not working in boardroom (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: ramesh.it042@company.com
- Subject: Projector not working

```
Projector not working in 4th Floor Boardroom
```

Reply sent:

- To: it.blr@company.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Projector not working in boardroom [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Projector not working in boardroom

New work order

Requester: Ramesh Kumar <ramesh.it042@company.com>
Type: IT support
Location: Karnataka > Bengaluru HQ
Team: IT - Bengaluru HQ
Due by: 18 Oct, 7:52 AM

Details:
- Location: 4th Floor Boardroom
- Issue: projector not working

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or priority is wrong, reply "cha…
```

- To: ramesh.it042@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Projector not working [ITS-2026-0001]

```
Dear Ramesh Kumar,

We have logged your request and assigned it to IT - Bengaluru HQ.

Request: ITS-2026-0001
Subject: Projector not working in boardroom
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

#### test_tc02_upward_fallback_region_faridabad_it — PASSED

What happened:

1. simran.hr112@company.com sent an email. Subject: "VPN and Charger issue". They wrote: "Need VPN access and laptop charger"
2. The desk opened ITS-2026-0001 (VPN and laptop charger) — handed to the team and still open.
3. It checked the records. Nothing in the records blocked it, so the desk carried on.
4. It wrote to it.north@company.com. Subject: "Work Order: VPN and laptop charger [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: VPN and laptop charger New work order Reques…"
5. It wrote to simran.hr112@company.com. Subject: "Re: VPN and Charger issue [ITS-2026-0001]". The message starts: "Dear Simran Kaur, We have logged your request and assigned it to IT - North Region. Request: ITS-2026-0001 Subject: VPN and laptop charger Status: Open You wil…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: VPN and laptop charger (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: simran.hr112@company.com
- Subject: VPN and Charger issue

```
Need VPN access and laptop charger
```

Reply sent:

- To: it.north@company.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: VPN and laptop charger [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: VPN and laptop charger

New work order

Requester: Simran Kaur <simran.hr112@company.com>
Type: Network / Wi-Fi
Location: Delhi NCR > Faridabad
Team: IT - North Region
Due by: 18 Oct, 7:52 AM

Details:
- Issue: VPN disconnected, need charger

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or priority is wrong, reply "change team to <team>", "change type …
```

- To: simran.hr112@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: VPN and Charger issue [ITS-2026-0001]

```
Dear Simran Kaur,

We have logged your request and assigned it to IT - North Region.

Request: ITS-2026-0001
Subject: VPN and laptop charger
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

#### test_tc03_upward_fallback_root_ranchi — PASSED

What happened:

1. alok.ops301@company.com sent an email. Subject: "Water dispenser leaking". They wrote: "Water dispenser leaking near reception"
2. The desk opened TKT-2026-0001 (Water dispenser leaking) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 6 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
4. It wrote to central-admin@company.com. Subject: "Work Order: Water dispenser leaking [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Water dispenser leaking Repair. No asset rec…"
5. It wrote to alok.ops301@company.com. Subject: "Re: Water dispenser leaking [TKT-2026-0001]". The message starts: "Dear Alok Verma, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-000…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Water dispenser leaking (ACTIVE, HIGH, stage DISPATCHED, decision REPAIR_UNKNOWN)

Email received:

- From: alok.ops301@company.com
- Subject: Water dispenser leaking

```
Water dispenser leaking near reception
```

Reply sent:

- To: central-admin@company.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Water dispenser leaking [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Water dispenser leaking

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 6

Requester: Alok Verma <alok.ops301@company.com>
Type: Plumbing
Location: East Corridor > Ranchi
Team: Facilities & Maintenance
Priority: High (time-critical signal: "leaking")
Due by: 18 Oct, 7:52 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: near reception
- Issue: leaking

Please reply to th…
```

- To: alok.ops301@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Water dispenser leaking [TKT-2026-0001]

```
Dear Alok Verma,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

#### test_tc04_explicit_location_override_visitor_to_mumbai — PASSED

What happened:

1. priya.fin88@company.com sent an email. Subject: "Chair broken at BKC". They wrote: "Visiting Mumbai BKC today. Chair wheel broken at Hotdesk 12B"
2. The desk opened TKT-2026-0001 (Chair wheel broken at Hotdesk 12B) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 4 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
4. It wrote to facilities.mumbai@company.com. Subject: "Work Order: Chair wheel broken at Hotdesk 12B [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Chair wheel broken at Hotdesk 12B Repair. No…"
5. It wrote to priya.fin88@company.com. Subject: "Re: Chair broken at BKC [TKT-2026-0001]". The message starts: "Dear Priya Shah, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-000…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Chair wheel broken at Hotdesk 12B (ACTIVE, HIGH, stage DISPATCHED, decision REPAIR_UNKNOWN)

Email received:

- From: priya.fin88@company.com
- Subject: Chair broken at BKC

```
Visiting Mumbai BKC today. Chair wheel broken at Hotdesk 12B
```

Reply sent:

- To: facilities.mumbai@company.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair wheel broken at Hotdesk 12B [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Chair wheel broken at Hotdesk 12B

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 4

Requester: Priya Shah <priya.fin88@company.com>
Type: Furniture
Location: Maharashtra > Mumbai BKC
Team: Facilities - Mumbai BKC
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:53 AM
Preferred vendor: BrightFurniture Co

Investigation:
Approved vendor on file: BrightFurniture Co; Route to Facilities - Mumbai BKC

Details:
- Location: Mumbai BKC
- Issue: chair wheel broken at Hotdesk 12B
- Item: chair wheel broken at Hotdesk 12B

Please reply to this email with one…
```

- To: priya.fin88@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Chair broken at BKC [TKT-2026-0001]

```
Dear Priya Shah,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities - Mumbai BKC.

Regards,
Workplace Team
```

#### test_tc05_missing_information_loop_catering — PASSED

What happened:

1. vikram.mkt09@company.com sent an email. Subject: "Catering tomorrow". They wrote: "Need lunch catering for client meeting tomorrow"
2. The desk opened CAT-2026-0001 (Lunch catering for client meeting) — waiting for the sender to reply with missing details.
3. It wrote to vikram.mkt09@company.com. Subject: "Re: Catering tomorrow [CAT-2026-0001]". The message starts: "Dear Vikram Mehta, Your request has been logged. Request: CAT-2026-0001 Subject: Lunch catering for client meeting Please reply with the following: - What time…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- CAT-2026-0001: Lunch catering for client meeting (ACTIVE, MEDIUM, stage AWAITING_INFO)

Email received:

- From: vikram.mkt09@company.com
- Subject: Catering tomorrow

```
Need lunch catering for client meeting tomorrow
```

Reply sent:

- To: vikram.mkt09@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Catering tomorrow [CAT-2026-0001]

```
Dear Vikram Mehta,

Your request has been logged.

Request: CAT-2026-0001
Subject: Lunch catering for client meeting

Please reply with the following:
- What time should it be ready?
- For how many people?

Regards,
Workplace Team
```

#### test_tc06_employee_gate_rejection — PASSED

What happened:

1. spammer123@gmail.com sent an email. Subject: "AC repair". They wrote: "Urgent: AC repair needed in Gurugram branch"
2. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: spammer123@gmail.com
- Subject: AC repair

```
Urgent: AC repair needed in Gurugram branch
```

#### test_team_done_reply_closes_without_duplicate — PASSED

What happened:

1. simran.hr112@company.com sent an email. Subject: "VPN and Charger issue". They wrote: "Need VPN access and laptop charger"
2. it.north@company.com sent an email. Subject: "Re: Work Order: VPN and charger [ITS-2026-0001]". They wrote: "Fixed. Charger delivered and VPN profile refreshed."
3. The desk opened ITS-2026-0001 (VPN and charger) — closed as done.
4. It checked the records. Nothing in the records blocked it, so the desk carried on.
5. It wrote to it.north@company.com. Subject: "Work Order: VPN and charger [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: VPN and charger New work order Requester: Si…"
6. It wrote to simran.hr112@company.com. Subject: "Re: VPN and Charger issue [ITS-2026-0001]". The message starts: "Dear Simran Kaur, We have logged your request and assigned it to IT - North Region. Request: ITS-2026-0001 Subject: VPN and charger Status: Open You will be up…"
7. It wrote to simran.hr112@company.com. Subject: "VPN and Charger issue [ITS-2026-0001]". The message starts: "Dear Simran Kaur, Good news - ITS-2026-0001 (VPN and charger) has been taken care of. Note from IT - North Region: Charger delivered and VPN refreshed If anyth…"
8. It wrote to central-admin@company.com, admin.faridabad@company.com. Subject: "Ops Update: VPN and charger [ITS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ITS-2026-0001 Subject: VPN and charger Completed by IT - North Region: Charger delivered and VPN refreshe…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: VPN and charger (RESOLVED, MEDIUM, stage RESOLVED, decision PROCEED)

Email received:

- From: simran.hr112@company.com
- Subject: VPN and Charger issue

```
Need VPN access and laptop charger
```

- From: it.north@company.com
- Subject: Re: Work Order: VPN and charger [ITS-2026-0001]

```
Fixed. Charger delivered and VPN profile refreshed.
```

Reply sent:

- To: it.north@company.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: VPN and charger [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: VPN and charger

New work order

Requester: Simran Kaur <simran.hr112@company.com>
Type: Network / Wi-Fi
Location: Delhi NCR > Faridabad
Team: IT - North Region
Due by: 18 Oct, 7:53 AM

Details:
- Issue: VPN disconnected

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or priority is wrong, reply "change team to <team>", "change type to <type>", or "chang…
```

- To: simran.hr112@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: VPN and Charger issue [ITS-2026-0001]

```
Dear Simran Kaur,

We have logged your request and assigned it to IT - North Region.

Request: ITS-2026-0001
Subject: VPN and charger
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

- To: simran.hr112@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: VPN and Charger issue [ITS-2026-0001]

```
Dear Simran Kaur,

Good news - ITS-2026-0001 (VPN and charger) has been taken care of.
Note from IT - North Region: Charger delivered and VPN refreshed

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: central-admin@company.com, admin.faridabad@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: VPN and charger [ITS-2026-0001]

```
Dear Team,

Please note the following update.

Request: ITS-2026-0001
Subject: VPN and charger

Completed by IT - North Region: Charger delivered and VPN refreshed

Requester: Simran Kaur <simran.hr112@company.com>
Type: Network / Wi-Fi
Location: Delhi NCR > Faridabad
Team: IT - North Region
Due by: 18 Oct, 7:53 AM

Details:
- Issue: VPN disconnected


Regards,
Workplace Team
```

#### test_edge_reopen_after_done_reuses_same_case — PASSED

What happened:

1. ramesh.it042@company.com sent an email. Subject: "Projector not working". They wrote: "Projector not working in 4th Floor Boardroom"
2. it.blr@company.com sent an email. Subject: "Re: Work Order: Projector not working [ITS-2026-0001]". They wrote: "done, projector replaced"
3. ramesh.it042@company.com sent an email. Subject: "Re: Projector not working [ITS-2026-0001]". They wrote: "Actually, it's still not working"
4. The desk opened ITS-2026-0001 (Projector not working) — handed to the team and still open.
5. It checked the records. Nothing in the records blocked it, so the desk carried on.
6. It wrote to it.blr@company.com. Subject: "Work Order: Projector not working [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Projector not working New work order Request…"
7. It wrote to ramesh.it042@company.com. Subject: "Re: Projector not working [ITS-2026-0001]". The message starts: "Dear Ramesh Kumar, We have logged your request and assigned it to IT - Bengaluru HQ. Request: ITS-2026-0001 Subject: Projector not working Status: Open You wil…"
8. It wrote to ramesh.it042@company.com. Subject: "Projector not working [ITS-2026-0001]". The message starts: "Dear Ramesh Kumar, Good news - ITS-2026-0001 (Projector not working) has been taken care of. Note from IT - Bengaluru HQ: Projector replaced If anything is sti…"
9. It wrote to central-admin@company.com. Subject: "Ops Update: Projector not working [ITS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ITS-2026-0001 Subject: Projector not working Completed by IT - Bengaluru HQ: Projector replaced Requester…"
10. It wrote to it.blr@company.com. Subject: "Work Order: Projector not working [ITS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ITS-2026-0001 Subject: Projector not working Thanks for completing this. To close it as verified, please …"
11. It wrote to it.blr@company.com. Subject: "Work Order: Projector not working [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Projector not working Reopened - requester s…"
12. It wrote to ramesh.it042@company.com. Subject: "Re: Projector not working [ITS-2026-0001]". The message starts: "Dear Ramesh Kumar, Request ITS-2026-0001 (Projector not working) has been reopened and returned to IT - Bengaluru HQ, together with your note. You will be upda…"
13. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Projector not working (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: ramesh.it042@company.com
- Subject: Projector not working

```
Projector not working in 4th Floor Boardroom
```

- From: it.blr@company.com
- Subject: Re: Work Order: Projector not working [ITS-2026-0001]

```
done, projector replaced
```

- From: ramesh.it042@company.com
- Subject: Re: Projector not working [ITS-2026-0001]

```
Actually, it's still not working
```

Reply sent:

- To: it.blr@company.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Projector not working [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Projector not working

New work order

Requester: Ramesh Kumar <ramesh.it042@company.com>
Type: IT support
Location: Karnataka > Bengaluru HQ
Team: IT - Bengaluru HQ
Due by: 18 Oct, 7:53 AM

Details:
- Location: 4th Floor Boardroom
- Issue: projector not working

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or priority is wrong, reply "change team to <…
```

- To: ramesh.it042@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Projector not working [ITS-2026-0001]

```
Dear Ramesh Kumar,

We have logged your request and assigned it to IT - Bengaluru HQ.

Request: ITS-2026-0001
Subject: Projector not working
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

- To: ramesh.it042@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Projector not working [ITS-2026-0001]

```
Dear Ramesh Kumar,

Good news - ITS-2026-0001 (Projector not working) has been taken care of.
Note from IT - Bengaluru HQ: Projector replaced

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: central-admin@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Projector not working [ITS-2026-0001]

```
Dear Team,

Please note the following update.

Request: ITS-2026-0001
Subject: Projector not working

Completed by IT - Bengaluru HQ: Projector replaced

Requester: Ramesh Kumar <ramesh.it042@company.com>
Type: IT support
Location: Karnataka > Bengaluru HQ
Team: IT - Bengaluru HQ
Due by: 18 Oct, 7:53 AM

Details:
- Location: 4th Floor Boardroom
- Issue: projector not working


Regards,
Workplace Team
```

- To: it.blr@company.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Projector not working [ITS-2026-0001]

```
Dear Team,

Please note the following update.

Request: ITS-2026-0001
Subject: Projector not working

Thanks for completing this. To close it as verified, please reply with what was done and the asset tag / ticket number if any (or attach a photo).

Requester: Ramesh Kumar <ramesh.it042@company.com>
Type: IT support
Location: Karnataka > Bengaluru HQ
Team: IT - Bengaluru HQ
Due by: 18 Oct, 7:53 AM

Details:
- Location: 4th Floor Boardroom
- Issue: projector not working


Regards,
Workplace Team
```

- To: it.blr@company.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Projector not working [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Projector not working

Reopened - requester says it is not sorted (reopen #1)

Requester: Ramesh Kumar <ramesh.it042@company.com>
Type: IT support
Location: Karnataka > Bengaluru HQ
Team: IT - Bengaluru HQ
Due by: 18 Oct, 7:53 AM

Details:
- Location: 4th Floor Boardroom
- Issue: projector not working
- Requester note: Actually, it's still not working

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, …
```

- To: ramesh.it042@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Projector not working [ITS-2026-0001]

```
Dear Ramesh Kumar,

Request ITS-2026-0001 (Projector not working) has been reopened and returned to IT - Bengaluru HQ, together with your note. You will be updated on this thread.

Regards,
Workplace Team
```

#### test_edge_duplicate_inbound_webhook_is_idempotent — PASSED

What happened:

1. simran.hr112@company.com sent an email. Subject: "VPN and Charger issue". They wrote: "Hi Admin, My VPN is disconnected and I need a replacement charger at my desk."
2. The desk opened ITS-2026-0001 (VPN and charger) — handed to the team and still open.
3. It checked the records. Nothing in the records blocked it, so the desk carried on.
4. It wrote to it.north@company.com. Subject: "Work Order: VPN and charger [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: VPN and charger New work order Requester: Si…"
5. It wrote to simran.hr112@company.com. Subject: "Re: VPN and Charger issue [ITS-2026-0001]". The message starts: "Dear Simran Kaur, We have logged your request and assigned it to IT - North Region. Request: ITS-2026-0001 Subject: VPN and charger Status: Open You will be up…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: VPN and charger (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: simran.hr112@company.com
- Subject: VPN and Charger issue

```
Hi Admin, My VPN is disconnected and I need a replacement charger at my desk.
```

Reply sent:

- To: it.north@company.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: VPN and charger [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: VPN and charger

New work order

Requester: Simran Kaur <simran.hr112@company.com>
Type: Network / Wi-Fi
Location: Delhi NCR > Faridabad
Team: IT - North Region
Due by: 18 Oct, 7:53 AM

Details:
- Issue: VPN disconnected

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or priority is wrong, reply "change team to <team>", "change type to <type>", or "chang…
```

- To: simran.hr112@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: VPN and Charger issue [ITS-2026-0001]

```
Dear Simran Kaur,

We have logged your request and assigned it to IT - North Region.

Request: ITS-2026-0001
Subject: VPN and charger
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

#### test_edge_ambiguous_delhi_office_asks_instead_of_home_branch — PASSED

What happened:

1. simran.hr112@company.com sent an email. Subject: "Printer issue". They wrote: "Please check the printer at the Delhi office"
2. The desk opened PRT-2026-0001 (Printer at Delhi office) — waiting for the sender to reply with missing details.
3. It wrote to simran.hr112@company.com. Subject: "Re: Printer issue [PRT-2026-0001]". The message starts: "Dear Simran Kaur, Your request has been logged. Request: PRT-2026-0001 Subject: Printer at Delhi office Please reply with the following: - What needs printing,…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- PRT-2026-0001: Printer at Delhi office (ACTIVE, MEDIUM, stage AWAITING_INFO)

Email received:

- From: simran.hr112@company.com
- Subject: Printer issue

```
Please check the printer at the Delhi office
```

Reply sent:

- To: simran.hr112@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Printer issue [PRT-2026-0001]

```
Dear Simran Kaur,

Your request has been logged.

Request: PRT-2026-0001
Subject: Printer at Delhi office

Please reply with the following:
- What needs printing, and how many?
- Which office is this at (Acme HQ Bengaluru, Ahmedabad SG, Amritsar, Bengaluru HQ, Bengaluru Whitefield, Bhubaneswar, Chandigarh, Chennai Guindy, … (31 offices — reply with the branch name))?

Regards,
Workplace Team
```

#### test_facilities_routing_per_branch[GGN-HQ] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[NOI-62] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[DEL-CP] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[FAR] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[CHD] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[LDH] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[ASR] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[KNL] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[MUM-BKC] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[MUM-AND] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[PUN-HJ] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[PUN-MG] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[NAG] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[NSK] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[AHM-SG] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[SUR] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[VAD] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[BLR-HQ] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[BLR-WF] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[MYS] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[CHN-OMR] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[CHN-GU] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[HYD-HIT] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[HYD-GAC] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[CBE] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[COK] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[KOL-SL] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[BBI] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[PAT] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_facilities_routing_per_branch[RAN] — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_admin_commands.py

11 cases, 0 failed.

#### test_rules_fallback_shape — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_normalize_gemini_output_is_defensive — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_reply_text_ignores_quoted_briefing — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_admin_approve_on_no_resource_informs_requester — PASSED

What happened:

1. Ops Desk <ops-desk@example.com> sent an email. Subject: "Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative". They wrote: "Approve On Sun, ops wrote: > OPS DECISION ..."
2. The desk opened ROOM-2026-0001 (Meeting for 80) — still open.
3. It wrote to big.team@company.com. Subject: "No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, No room fits 80 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40 o…"
4. It wrote to ops-desk@example.com. Subject: "Ops Decision: No suitable room in inventory [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: No suitable room in inventory No room fits 80 people in person (largest inventory room holds 40). Requester: b…"
5. It wrote to big.team@company.com. Subject: "Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, Thanks — we've recorded your choice: Escalate for a larger venue / off-site option. Our ops team will take it from here and follow up on this ca…"
6. It wrote to ops-desk@example.com. Subject: "Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Requester selected alternative — Escalate for a larger venue / off-site option Follow through on this alternat…"
7. It wrote to big.team@company.com. Subject: "Ops Approved: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, Ops has approved a larger venue / off-site option for your meeting. We're arranging the venue now and will send you the confirmed location short…"
8. It wrote to ops-desk@example.com. Subject: "Ops Done: APPROVE: Approved requester alternative: Escalate for a larger venue / off-site option. Re [ROOM-2026-0001]". The message starts: "Done — Approved requester alternative: Escalate for a larger venue / off-site option. Requester informed. Next: once the venue is fixed, just reply with it (e.…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 80 (ACTIVE, MEDIUM)

Email received:

- From: Ops Desk <ops-desk@example.com>
- Subject: Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative

```
Approve

On Sun, ops wrote:
> OPS DECISION ...
```

Reply sent:

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

No room fits 80 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: No suitable room in inventory [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: No suitable room in inventory
No room fits 80 people in person (largest inventory room holds 40).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — No room fits 80 people in person (largest inventory room holds 40).

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

Thanks — we've recorded your choice: Escalate for a larger venue / off-site option.
Our ops team will take it from here and follow up on this case.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Requester selected alternative — Escalate for a larger venue / off-site option
Follow through on this alternative (book off-site, split, reschedule, etc.).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — requester picked: Escalate for a larger venue / off-site option

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Approved: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

Ops has approved a larger venue / off-site option for your meeting. We're arranging the venue now and will send you the confirmed location shortly.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Done: APPROVE: Approved requester alternative: Escalate for a larger venue / off-site option. Re [ROOM-2026-0001]

```
Done — Approved requester alternative: Escalate for a larger venue / off-site option. Requester informed.
Next: once the venue is fixed, just reply with it (e.g. "book Hyatt ballroom") — the requester gets the confirmation.

Case: ROOM-2026-0001
```

#### test_admin_book_offsite_resolves_exception — PASSED

What happened:

1. Ops Desk <ops-desk@example.com> sent an email. Subject: "Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative". They wrote: "book Hyatt Regency Ballroom"
2. The desk opened ROOM-2026-0001 (Meeting for 80) — still open.
3. It wrote to big.team@company.com. Subject: "No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, No room fits 80 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40 o…"
4. It wrote to ops-desk@example.com. Subject: "Ops Decision: No suitable room in inventory [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: No suitable room in inventory No room fits 80 people in person (largest inventory room holds 40). Requester: b…"
5. It wrote to big.team@company.com. Subject: "Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, Thanks — we've recorded your choice: Escalate for a larger venue / off-site option. Our ops team will take it from here and follow up on this ca…"
6. It wrote to ops-desk@example.com. Subject: "Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Requester selected alternative — Escalate for a larger venue / off-site option Follow through on this alternat…"
7. It wrote to big.team@company.com. Subject: "Booking Confirmed: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, Your meeting room booking is confirmed. Room: Hyatt Regency Ballroom Case: ROOM-2026-0001 Hold window: 2:00 PM (setup 30m earlier) – 5:00 PM (+1…"
8. It wrote to ops-desk@example.com. Subject: "Ops Decision: Booking confirmed — Hyatt Regency Ballroom [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Hyatt Regency Ballroom Requester: big.team@company.com When: Tue 22 Sep 2026, 2:00 PM–5:00…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 80 (ACTIVE, MEDIUM)

Email received:

- From: Ops Desk <ops-desk@example.com>
- Subject: Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative

```
book Hyatt Regency Ballroom
```

Reply sent:

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

No room fits 80 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: No suitable room in inventory [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: No suitable room in inventory
No room fits 80 people in person (largest inventory room holds 40).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — No room fits 80 people in person (largest inventory room holds 40).

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

Thanks — we've recorded your choice: Escalate for a larger venue / off-site option.
Our ops team will take it from here and follow up on this case.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Requester selected alternative — Escalate for a larger venue / off-site option
Follow through on this alternative (book off-site, split, reschedule, etc.).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — requester picked: Escalate for a larger venue / off-site option

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

Your meeting room booking is confirmed.

Room: Hyatt Regency Ballroom
Case: ROOM-2026-0001
Hold window: 2:00 PM (setup 30m earlier) – 5:00 PM (+15m release)

Active preparations: AV/display.
No separate approval is needed for installed AV / VC and internal IT support. Cost approval will cover only external / off-site venue.
The chargeable items are waiting for cost approval — everything else goes ahead now, and I'll confirm once it's approved.
Assumptions:
- Video conferencing treated as not required under internal-meeting rule MP-INT-006; reply to correct before the change cutoff.


When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Booking confirmed — Hyatt Regency Ballroom [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Hyatt Regency Ballroom

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
Room: Hyatt Regency Ballroom (80 seats), setup 30 min before
People: 80

To arrange:
- Display / screen
- Orchestrator role: module_helper

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Final room inspection before setup time
    · Clean and reset Hyatt Regency Ballroom after the meeting
- IT / AV: with you (no IT Support mailbox set yet)
    · Display / projector working
    · AV test done by 22 Sep, 1:30 PM
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

Cost approval needed — it covers only the chargeable part:
Cost centre: not given yet (asked from the requester)
Chargeable:
- Externa…
```

#### test_admin_reject_asks_requester_for_another_option — PASSED

What happened:

1. Ops Desk <ops-desk@example.com> sent an email. Subject: "Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative". They wrote: "reject - no off-site budget"
2. The desk opened ROOM-2026-0001 (Meeting for 80) — still open.
3. It wrote to big.team@company.com. Subject: "No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, No room fits 80 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40 o…"
4. It wrote to ops-desk@example.com. Subject: "Ops Decision: No suitable room in inventory [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: No suitable room in inventory No room fits 80 people in person (largest inventory room holds 40). Requester: b…"
5. It wrote to big.team@company.com. Subject: "Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, Thanks — we've recorded your choice: Escalate for a larger venue / off-site option. Our ops team will take it from here and follow up on this ca…"
6. It wrote to ops-desk@example.com. Subject: "Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Requester selected alternative — Escalate for a larger venue / off-site option Follow through on this alternat…"
7. It wrote to big.team@company.com. Subject: "Ops Update: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, Our ops team couldn't arrange Escalate for a larger venue / off-site option. Reason: no off-site budget Please reply with another option: - Redu…"
8. It wrote to ops-desk@example.com. Subject: "Ops Done: REJECT: Alternative rejected; requester asked to pick another. [ROOM-2026-0001]". The message starts: "Done — Alternative rejected; requester asked to pick another. Case: ROOM-2026-0001"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 80 (ACTIVE, MEDIUM)

Email received:

- From: Ops Desk <ops-desk@example.com>
- Subject: Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative

```
reject - no off-site budget
```

Reply sent:

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

No room fits 80 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: No suitable room in inventory [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: No suitable room in inventory
No room fits 80 people in person (largest inventory room holds 40).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — No room fits 80 people in person (largest inventory room holds 40).

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

Thanks — we've recorded your choice: Escalate for a larger venue / off-site option.
Our ops team will take it from here and follow up on this case.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Requester selected alternative — Escalate for a larger venue / off-site option
Follow through on this alternative (book off-site, split, reschedule, etc.).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — requester picked: Escalate for a larger venue / off-site option

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Update: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

Our ops team couldn't arrange Escalate for a larger venue / off-site option. Reason: no off-site budget

Please reply with another option:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Done: REJECT: Alternative rejected; requester asked to pick another. [ROOM-2026-0001]

```
Done — Alternative rejected; requester asked to pick another.

Case: ROOM-2026-0001
```

#### test_admin_unknown_reply_changes_nothing — PASSED

What happened:

1. Ops Desk <ops-desk@example.com> sent an email. Subject: "Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative". They wrote: "let me check with facilities"
2. The desk opened ROOM-2026-0001 (Meeting for 80) — still open.
3. It wrote to big.team@company.com. Subject: "No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, No room fits 80 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40 o…"
4. It wrote to ops-desk@example.com. Subject: "Ops Decision: No suitable room in inventory [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: No suitable room in inventory No room fits 80 people in person (largest inventory room holds 40). Requester: b…"
5. It wrote to big.team@company.com. Subject: "Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, Thanks — we've recorded your choice: Escalate for a larger venue / off-site option. Our ops team will take it from here and follow up on this ca…"
6. It wrote to ops-desk@example.com. Subject: "Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Requester selected alternative — Escalate for a larger venue / off-site option Follow through on this alternat…"
7. It wrote to ops-desk@example.com. Subject: "Ops Not Applied: NONE: Nothing actionable in your reply — nothing was changed. [ROOM-2026-0001]". The message starts: "Not done — Nothing actionable in your reply — nothing was changed. I read your reply as: No actionable instruction found Reply again in plain words, e.g. "appr…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 80 (ACTIVE, MEDIUM)

Email received:

- From: Ops Desk <ops-desk@example.com>
- Subject: Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative

```
let me check with facilities
```

Reply sent:

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

No room fits 80 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: No suitable room in inventory [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: No suitable room in inventory
No room fits 80 people in person (largest inventory room holds 40).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — No room fits 80 people in person (largest inventory room holds 40).

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

Thanks — we've recorded your choice: Escalate for a larger venue / off-site option.
Our ops team will take it from here and follow up on this case.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Requester selected alternative — Escalate for a larger venue / off-site option
Follow through on this alternative (book off-site, split, reschedule, etc.).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — requester picked: Escalate for a larger venue / off-site option

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Not Applied: NONE: Nothing actionable in your reply — nothing was changed. [ROOM-2026-0001]

```
Not done — Nothing actionable in your reply — nothing was changed.
I read your reply as: No actionable instruction found
Reply again in plain words, e.g. "approve", "book F2-R3" or "make it 20 people".

Case: ROOM-2026-0001
```

#### test_gemini_reads_free_text_book_plus_message — PASSED

What happened:

1. Ops Desk <ops-desk@example.com> sent an email. Subject: "Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative". They wrote: "haan theek hai, hyatt ballroom le lo unke liye. bol dena monday 11 baje venue dekh sakte hai"
2. The desk opened ROOM-2026-0001 (Meeting for 80) — still open.
3. It wrote to big.team@company.com. Subject: "No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, No room fits 80 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40 o…"
4. It wrote to ops-desk@example.com. Subject: "Ops Decision: No suitable room in inventory [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: No suitable room in inventory No room fits 80 people in person (largest inventory room holds 40). Requester: b…"
5. It wrote to big.team@company.com. Subject: "Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, Thanks — we've recorded your choice: Escalate for a larger venue / off-site option. Our ops team will take it from here and follow up on this ca…"
6. It wrote to ops-desk@example.com. Subject: "Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Requester selected alternative — Escalate for a larger venue / off-site option Follow through on this alternat…"
7. It wrote to big.team@company.com. Subject: "Booking Confirmed: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, Your meeting room booking is confirmed. Room: Hyatt Regency Ballroom Case: ROOM-2026-0001 Hold window: 2:00 PM (setup 30m earlier) – 5:00 PM (+1…"
8. It wrote to ops-desk@example.com. Subject: "Ops Decision: Booking confirmed — Hyatt Regency Ballroom [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Hyatt Regency Ballroom Requester: big.team@company.com When: Tue 22 Sep 2026, 2:00 PM–5:00…"
9. It wrote to big.team@company.com. Subject: "Update From Ops: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, We have a venue walkthrough on Monday at 11am if you'd like to join. Case: ROOM-2026-0001"
10. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 80 (ACTIVE, MEDIUM)

Email received:

- From: Ops Desk <ops-desk@example.com>
- Subject: Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative

```
haan theek hai, hyatt ballroom le lo unke liye. bol dena monday 11 baje venue dekh sakte hai
```

Reply sent:

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

No room fits 80 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: No suitable room in inventory [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: No suitable room in inventory
No room fits 80 people in person (largest inventory room holds 40).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — No room fits 80 people in person (largest inventory room holds 40).

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

Thanks — we've recorded your choice: Escalate for a larger venue / off-site option.
Our ops team will take it from here and follow up on this case.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Requester selected alternative — Escalate for a larger venue / off-site option
Follow through on this alternative (book off-site, split, reschedule, etc.).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — requester picked: Escalate for a larger venue / off-site option

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

Your meeting room booking is confirmed.

Room: Hyatt Regency Ballroom
Case: ROOM-2026-0001
Hold window: 2:00 PM (setup 30m earlier) – 5:00 PM (+15m release)

Active preparations: AV/display.
No separate approval is needed for installed AV / VC and internal IT support. Cost approval will cover only external / off-site venue.
The chargeable items are waiting for cost approval — everything else goes ahead now, and I'll confirm once it's approved.
Assumptions:
- Video conferencing treated as not required under internal-meeting rule MP-INT-006; reply to correct before the change cutoff.


When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Booking confirmed — Hyatt Regency Ballroom [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Hyatt Regency Ballroom

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
Room: Hyatt Regency Ballroom (80 seats), setup 30 min before
People: 80

To arrange:
- Display / screen
- Orchestrator role: module_helper

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Final room inspection before setup time
    · Clean and reset Hyatt Regency Ballroom after the meeting
- IT / AV: with you (no IT Support mailbox set yet)
    · Display / projector working
    · AV test done by 22 Sep, 1:30 PM
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

Cost approval needed — it covers only the chargeable part:
Cost centre: not given yet (asked from the requester)
Chargeable:
- Externa…
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Update From Ops: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

We have a venue walkthrough on Monday at 11am if you'd like to join.

Case: ROOM-2026-0001
```

#### test_gemini_fact_update_reruns_search — PASSED

What happened:

1. Ops Desk <ops-desk@example.com> sent an email. Subject: "Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative". They wrote: "only 8 of them are actually coming, sort it"
2. The desk opened ROOM-2026-0001 (Meeting for 80) — still open.
3. It wrote to big.team@company.com. Subject: "No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, No room fits 80 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40 o…"
4. It wrote to ops-desk@example.com. Subject: "Ops Decision: No suitable room in inventory [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: No suitable room in inventory No room fits 80 people in person (largest inventory room holds 40). Requester: b…"
5. It wrote to big.team@company.com. Subject: "Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, Thanks — we've recorded your choice: Escalate for a larger venue / off-site option. Our ops team will take it from here and follow up on this ca…"
6. It wrote to ops-desk@example.com. Subject: "Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Requester selected alternative — Escalate for a larger venue / off-site option Follow through on this alternat…"
7. It wrote to big.team@company.com. Subject: "Confirm Booking: Meeting for 8 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, Good news — I found a room that fits and I'm holding it for you. Room: Focus Room 5A (seats 8) Your booking: - Attendees: 8 - Date: 22 September…"
8. It wrote to ops-desk@example.com. Subject: "Ops Done: UPDATE_FACTS: Updated attendees → 8; re-ran room search. Proposed Focus Room 5A to the req [ROOM-2026-0001]". The message starts: "Done — Updated attendees → 8; re-ran room search. Proposed Focus Room 5A to the requester. Changed: attendees → 8 Case: ROOM-2026-0001"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 80 (ACTIVE, MEDIUM)

Email received:

- From: Ops Desk <ops-desk@example.com>
- Subject: Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative

```
only 8 of them are actually coming, sort it
```

Reply sent:

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

No room fits 80 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: No suitable room in inventory [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: No suitable room in inventory
No room fits 80 people in person (largest inventory room holds 40).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — No room fits 80 people in person (largest inventory room holds 40).

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

Thanks — we've recorded your choice: Escalate for a larger venue / off-site option.
Our ops team will take it from here and follow up on this case.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Requester selected alternative — Escalate for a larger venue / off-site option
Follow through on this alternative (book off-site, split, reschedule, etc.).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — requester picked: Escalate for a larger venue / off-site option

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 8 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

Good news — I found a room that fits and I'm holding it for you.

Room: Focus Room 5A (seats 8)

Your booking:
- Attendees: 8
- Date: 22 September 2026
- Time: 2:00 PM – 5:00 PM
- Meeting type: internal meeting
- Presentation display: yes
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

Please double-check:
- Hybrid / AV: no

I've set these for you — reply if any should change:
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Done: UPDATE_FACTS: Updated attendees → 8; re-ran room search. Proposed Focus Room 5A to the req [ROOM-2026-0001]

```
Done — Updated attendees → 8; re-ran room search. Proposed Focus Room 5A to the requester.
Changed: attendees → 8

Case: ROOM-2026-0001
```

#### test_gemini_unsure_changes_nothing — PASSED

What happened:

1. Ops Desk <ops-desk@example.com> sent an email. Subject: "Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative". They wrote: "book the one we discussed"
2. The desk opened ROOM-2026-0001 (Meeting for 80) — still open.
3. It wrote to big.team@company.com. Subject: "No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, No room fits 80 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40 o…"
4. It wrote to ops-desk@example.com. Subject: "Ops Decision: No suitable room in inventory [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: No suitable room in inventory No room fits 80 people in person (largest inventory room holds 40). Requester: b…"
5. It wrote to big.team@company.com. Subject: "Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, Thanks — we've recorded your choice: Escalate for a larger venue / off-site option. Our ops team will take it from here and follow up on this ca…"
6. It wrote to ops-desk@example.com. Subject: "Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Requester selected alternative — Escalate for a larger venue / off-site option Follow through on this alternat…"
7. It wrote to ops-desk@example.com. Subject: "Ops Not Applied: BOOK: Which venue should I book — the Hyatt or the auditorium? [ROOM-2026-0001]". The message starts: "Not done — Which venue should I book — the Hyatt or the auditorium? I read your reply as: Book Reply again in plain words, e.g. "approve", "book F2-R3" or "mak…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 80 (ACTIVE, MEDIUM)

Email received:

- From: Ops Desk <ops-desk@example.com>
- Subject: Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative

```
book the one we discussed
```

Reply sent:

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

No room fits 80 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: No suitable room in inventory [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: No suitable room in inventory
No room fits 80 people in person (largest inventory room holds 40).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — No room fits 80 people in person (largest inventory room holds 40).

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

Thanks — we've recorded your choice: Escalate for a larger venue / off-site option.
Our ops team will take it from here and follow up on this case.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Requester selected alternative — Escalate for a larger venue / off-site option
Follow through on this alternative (book off-site, split, reschedule, etc.).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — requester picked: Escalate for a larger venue / off-site option

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Not Applied: BOOK: Which venue should I book — the Hyatt or the auditorium? [ROOM-2026-0001]

```
Not done — Which venue should I book — the Hyatt or the auditorium?
I read your reply as: Book
Reply again in plain words, e.g. "approve", "book F2-R3" or "make it 20 people".

Case: ROOM-2026-0001
```

#### test_gemini_outage_falls_back_to_rules — PASSED

What happened:

1. Ops Desk <ops-desk@example.com> sent an email. Subject: "Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative". They wrote: "Approve"
2. The desk opened ROOM-2026-0001 (Meeting for 80) — still open.
3. It wrote to big.team@company.com. Subject: "No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, No room fits 80 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40 o…"
4. It wrote to ops-desk@example.com. Subject: "Ops Decision: No suitable room in inventory [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: No suitable room in inventory No room fits 80 people in person (largest inventory room holds 40). Requester: b…"
5. It wrote to big.team@company.com. Subject: "Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, Thanks — we've recorded your choice: Escalate for a larger venue / off-site option. Our ops team will take it from here and follow up on this ca…"
6. It wrote to ops-desk@example.com. Subject: "Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Requester selected alternative — Escalate for a larger venue / off-site option Follow through on this alternat…"
7. It wrote to big.team@company.com. Subject: "Ops Approved: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, Ops has approved a larger venue / off-site option for your meeting. We're arranging the venue now and will send you the confirmed location short…"
8. It wrote to ops-desk@example.com. Subject: "Ops Done: APPROVE: Approved requester alternative: Escalate for a larger venue / off-site option. Re [ROOM-2026-0001]". The message starts: "Done — Approved requester alternative: Escalate for a larger venue / off-site option. Requester informed. Next: once the venue is fixed, just reply with it (e.…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 80 (ACTIVE, MEDIUM)

Email received:

- From: Ops Desk <ops-desk@example.com>
- Subject: Re: [OPS DECISION] [ROOM-2026-0001] OPS DECISION: Requester selected alternative

```
Approve
```

Reply sent:

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

No room fits 80 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: No suitable room in inventory [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: No suitable room in inventory
No room fits 80 people in person (largest inventory room holds 40).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — No room fits 80 people in person (largest inventory room holds 40).

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

Thanks — we've recorded your choice: Escalate for a larger venue / off-site option.
Our ops team will take it from here and follow up on this case.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Requester selected alternative — Escalate for a larger venue / off-site option
Follow through on this alternative (book off-site, split, reschedule, etc.).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — requester picked: Escalate for a larger venue / off-site option

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Approved: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

Ops has approved a larger venue / off-site option for your meeting. We're arranging the venue now and will send you the confirmed location shortly.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Done: APPROVE: Approved requester alternative: Escalate for a larger venue / off-site option. Re [ROOM-2026-0001]

```
Done — Approved requester alternative: Escalate for a larger venue / off-site option. Requester informed.
Next: once the venue is fixed, just reply with it (e.g. "book Hyatt ballroom") — the requester gets the confirmation.

Case: ROOM-2026-0001
```

### test_admin_desk.py

8 cases, 0 failed.

#### test_hi_gets_a_helpful_reply_and_no_case — PASSED

What happened:

1. kapil.mantri@herofincorp.com sent an email. Subject: "hi". They wrote: "Hi [Hero-Logo.jpg] Kapil Mantri Sr. Associate"
2. It wrote to kapil.mantri@herofincorp.com. Subject: "Re: hi". The message starts: "Hi Kapil, Good to hear from you! This is the Admin Desk - I can help with repairs and facility issues, IT help, housekeeping, visitor passes, parking, gate pas…"
3. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: kapil.mantri@herofincorp.com
- Subject: hi

```
Hi

[Hero-Logo.jpg]

Kapil Mantri
Sr. Associate
```

Reply sent:

- To: kapil.mantri@herofincorp.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: hi

```
Hi Kapil,

Good to hear from you! This is the Admin Desk - I can help with repairs and facility issues, IT help, housekeeping, visitor passes, parking, gate passes, couriers, office supplies, travel and cabs, seating, events, onboarding and meeting rooms.

How can I help you today? Just reply with what you need.

Workplace Team
```

#### test_empty_mail_asks_to_resend — PASSED

What happened:

1. kapil.mantri@herofincorp.com sent an email. Subject: "RE: request". They wrote: "<Logo.jpg> Kapil Mantri Sr. Associate"
2. It wrote to kapil.mantri@herofincorp.com. Subject: "Re: request". The message starts: "Hi Kapil, Your mail seems to have come through empty - could you resend it with the details? Workplace Team"
3. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: kapil.mantri@herofincorp.com
- Subject: RE: request

```
<Logo.jpg>

Kapil Mantri
Sr. Associate
```

Reply sent:

- To: kapil.mantri@herofincorp.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: request

```
Hi Kapil,

Your mail seems to have come through empty - could you resend it with the details?

Workplace Team
```

#### test_rules_fallback_logs_a_repair_without_gemini — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "AC issue". They wrote: "AC not working in 4th floor bay near pantry, very hot"
2. The desk opened TKT-2026-0001 (AC not working in 4th floor bay near pantry, very hot) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to ops-desk@example.com. Subject: "Work Order: AC not working in 4th floor bay near pantry, very hot [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: AC not working in 4th floor bay near pantry,…"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: AC issue [TKT-2026-0001]". The message starts: "Hi Arjun, Thanks for letting us know. I've logged this as TKT-2026-0001 and passed it to the right team - we'll keep you posted here. Workplace Team"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: AC not working in 4th floor bay near pantry, very hot (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: AC issue

```
AC not working in 4th floor bay near pantry, very hot
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: AC not working in 4th floor bay near pantry, very hot [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: AC not working in 4th floor bay near pantry, very hot

Repair This item. Repairs on record: 0 of 6.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Air conditioning
Team: Facilities & Maintenance
Due by: 18 Oct, 7:46 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

What they asked: AC not working in 4th floor bay near pantry, very hot

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue:…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: AC issue [TKT-2026-0001]

```
Hi Arjun,

Thanks for letting us know. I've logged this as TKT-2026-0001 and passed it to the right team - we'll keep you posted here.

Workplace Team
```

#### test_one_mail_two_requests_become_two_cases — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "tap leaking in 3rd floor washroom. also 2 visitors friday 11am Rahul Sharma (Infosys), Aman Verma (TCS)"
2. The desk opened TKT-2026-0001 (Leaking tap in 3rd floor washroom) — handed to the team and still open; VIS-2026-0001 (Visitors on Friday) — completed.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to ops-desk@example.com. Subject: "Work Order: Leaking tap in 3rd floor washroom [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Leaking tap in 3rd floor washroom Repair Thi…"
5. It wrote to ops-desk@example.com. Subject: "Done: Visitors on Friday [VIS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: VIS-2026-0001 Subject: Visitors on Friday Visitor pre-registered - add to today's gate manifest (No Secur…"
6. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [TKT-2026-0001] [VIS-2026-0001]". The message starts: "Hi Arjun, I've logged the leaking tap as TKT-2026-0001 and registered your visitors under VIS-2026-0001. Workplace Team"
7. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Leaking tap in 3rd floor washroom (ACTIVE, HIGH, stage DISPATCHED, decision REPAIR)
- VIS-2026-0001: Visitors on Friday (ACTIVE, HIGH, stage COMPLETED, decision PROCEED)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
tap leaking in 3rd floor washroom. also 2 visitors friday 11am Rahul Sharma (Infosys), Aman Verma (TCS)
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Leaking tap in 3rd floor washroom [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Leaking tap in 3rd floor washroom

Repair This item. Repairs on record: 0 of 6.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Priority: High (time-critical signal: "leaking")
Due by: 18 Oct, 7:46 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: 3rd floor washroom
- Issue: tap leaking
- Time: 11am

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to upd…
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Done: Visitors on Friday [VIS-2026-0001]

```
Dear Team,

Please note the following update.

Request: VIS-2026-0001
Subject: Visitors on Friday

Visitor pre-registered - add to today's gate manifest
(No Security & Front Desk contact set yet - sent to you. Add it in Company setup.)

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Visitor pre-registration
Team: Security & Front Desk
Priority: High (time-critical signal: "leaking")
Due by: 18 Oct, 3:46 AM

Details:
- Visit date: Friday 9 Oct
- Visitor names: Rahul Sharma (Infosys), Aman Verma (TCS)
- Time: 11 AM
- Pass VP-C9FA41: Rahul Sharma (Infosys)
- Pass VP-3A08DC: Aman Verma (TCS)


Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [TKT-2026-0001] [VIS-2026-0001]

```
Hi Arjun,

I've logged the leaking tap as TKT-2026-0001 and registered your visitors under VIS-2026-0001.

Workplace Team
```

#### test_sensitive_request_waits_for_admin_then_proceeds — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "Need access to the server room from Monday"
2. Ops <ops-desk@example.com> sent an email. Subject: "Re: Ops Decision: Server room access for Arjun [ITS-2026-0001]". They wrote: "approve"
3. The desk opened ITS-2026-0001 (Server room access for Arjun) — handed to the team and still open.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 3 repairs. The records did not call for a replacement, so this stayed a normal repair.
5. It wrote to ops-desk@example.com. Subject: "Ops Decision: Server room access for Arjun [ITS-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: ITS-2026-0001 Subject: Server room access for Arjun Needs your approval - access car…"
6. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [ITS-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged and sent for approval. Request: ITS-2026-0001 Subject: Server room access for Arjun You will be updated on this …"
7. It wrote to ops-desk@example.com. Subject: "Ops Decision: Server room access for Arjun [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Server room access for Arjun Repair This ite…"
8. It wrote to arjun.singh@acme.demo. Subject: "Request [ITS-2026-0001]". The message starts: "Dear Arjun Singh, Request ITS-2026-0001 (Server room access for Arjun) is approved and assigned to IT Support. You will be updated on this thread when the work…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Server room access for Arjun (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
Need access to the server room from Monday
```

- From: Ops <ops-desk@example.com>
- Subject: Re: Ops Decision: Server room access for Arjun [ITS-2026-0001]

```
approve
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Server room access for Arjun [ITS-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: ITS-2026-0001
Subject: Server room access for Arjun

Needs your approval - access card requests need admin sign-off

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 3

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Access card / ID
Team: IT Support

Details:
- Area: server room

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [ITS-2026-0001]

```
Dear Arjun Singh,

Your request has been logged and sent for approval.

Request: ITS-2026-0001
Subject: Server room access for Arjun

You will be updated on this thread once a decision is recorded.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Server room access for Arjun [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Server room access for Arjun

Repair This item. Repairs on record: 0 of 3.
(No IT Support contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 3

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Access card / ID
Team: IT Support
Due by: 18 Oct, 7:46 AM

Details:
- Area: server room

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <the card number issued or access granted>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Request [ITS-2026-0001]

```
Dear Arjun Singh,

Request ITS-2026-0001 (Server room access for Arjun) is approved and assigned to IT Support. You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

#### test_department_done_closes_loop_with_requester — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "cleaning". They wrote: "Washroom on 2nd floor needs cleaning urgently"
2. housekeeping@acme-real.com sent an email. Subject: "Re: Work Order: Washroom on 2nd floor needs cleaning urgently [TKT-2026-0001]". They wrote: "done, cleaned and restocked"
3. The desk opened TKT-2026-0001 (Washroom on 2nd floor needs cleaning urgently) — closed as done.
4. It checked the records. Nothing in the records blocked it, so the desk carried on.
5. It wrote to housekeeping@acme-real.com. Subject: "Work Order: Washroom on 2nd floor needs cleaning urgently [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Washroom on 2nd floor needs cleaning urgentl…"
6. It wrote to arjun.singh@acme.demo. Subject: "Re: cleaning [TKT-2026-0001]". The message starts: "Hi Arjun, Thanks for letting us know. I've logged this as TKT-2026-0001 and passed it to the right team - we'll keep you posted here. Workplace Team"
7. It wrote to arjun.singh@acme.demo. Subject: "cleaning [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Good news - TKT-2026-0001 (Washroom on 2nd floor needs cleaning urgently) has been taken care of. Note from Housekeeping: cleaned and restock…"
8. It wrote to ops-desk@example.com. Subject: "Ops Update: Washroom on 2nd floor needs cleaning urgently [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Washroom on 2nd floor needs cleaning urgently Completed by Housekeeping: cleaned a…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Washroom on 2nd floor needs cleaning urgently (RESOLVED, HIGH, stage RESOLVED, decision PROCEED)

Email received:

- From: arjun.singh@acme.demo
- Subject: cleaning

```
Washroom on 2nd floor needs cleaning urgently
```

- From: housekeeping@acme-real.com
- Subject: Re: Work Order: Washroom on 2nd floor needs cleaning urgently [TKT-2026-0001]

```
done, cleaned and restocked
```

Reply sent:

- To: housekeeping@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Washroom on 2nd floor needs cleaning urgently [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Washroom on 2nd floor needs cleaning urgently

High-priority work order

Record check:
- Place: 2nd floor
- Earlier completions at this place: 0
- Escalate after: 4

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Housekeeping
Team: Housekeeping
Priority: High (time-critical signal: "urgently")
Due by: 18 Oct, 3:46 AM

What they asked: Washroom on 2nd floor needs cleaning urgently

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that …
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: cleaning [TKT-2026-0001]

```
Hi Arjun,

Thanks for letting us know. I've logged this as TKT-2026-0001 and passed it to the right team - we'll keep you posted here.

Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: cleaning [TKT-2026-0001]

```
Dear Arjun Singh,

Good news - TKT-2026-0001 (Washroom on 2nd floor needs cleaning urgently) has been taken care of.
Note from Housekeeping: cleaned and restocked

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Washroom on 2nd floor needs cleaning urgently [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Washroom on 2nd floor needs cleaning urgently

Completed by Housekeeping: cleaned and restocked

Record check:
- Place: 2nd floor
- Earlier completions at this place: 0
- Escalate after: 4

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Housekeeping
Team: Housekeeping
Priority: High (time-critical signal: "urgently")
Due by: 18 Oct, 3:46 AM

What they asked: Washroom on 2nd floor needs cleaning urgently


Regards,
Workplace Team
```

#### test_status_question_answers_from_case_state — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "printer". They wrote: "Printer on 1st floor not working"
2. arjun.singh@acme.demo sent an email. Subject: "Re: printer". They wrote: "any update?"
3. The desk opened TKT-2026-0001 (Printer on 1st floor not working) — handed to the team and still open.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
5. It wrote to ops-desk@example.com. Subject: "Work Order: Printer on 1st floor not working [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Printer on 1st floor not working Repair This…"
6. It wrote to arjun.singh@acme.demo. Subject: "Re: printer [TKT-2026-0001]". The message starts: "Hi Arjun, Thanks for letting us know. I've logged this as TKT-2026-0001 and passed it to the right team - we'll keep you posted here. Workplace Team"
7. It wrote to arjun.singh@acme.demo. Subject: "Re: printer [TKT-2026-0001]". The message starts: "Hi Arjun, TKT-2026-0001 is with IT Support. Workplace Team"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Printer on 1st floor not working (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: printer

```
Printer on 1st floor not working
```

- From: arjun.singh@acme.demo
- Subject: Re: printer

```
any update?
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Printer on 1st floor not working [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Printer on 1st floor not working

Repair This item. Repairs on record: 0 of 6.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:46 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

What they asked: Printer on 1st floor not working

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: printer [TKT-2026-0001]

```
Hi Arjun,

Thanks for letting us know. I've logged this as TKT-2026-0001 and passed it to the right team - we'll keep you posted here.

Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: printer [TKT-2026-0001]

```
Hi Arjun,

TKT-2026-0001 is with IT Support.

Workplace Team
```

#### test_meeting_room_request_goes_to_room_flow — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "Need a meeting room for 8 people tomorrow 3-5pm at Corporate Office, internal review"
2. The desk opened ROOM-2026-0001 (Meeting for 8 on tomorrow at 5pm) — still open.
3. It wrote to arjun.singh@acme.demo. Subject: "Information required: Meeting for 8 on tomorrow at 5pm [ROOM-2026-0001]". The message starts: "Dear Arjun Singh, Thanks for your meeting-room request — it's registered as ROOM-2026-0001. Here's what I have so far: - Attendees: 8 - Date: tomorrow - Start:…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 8 on tomorrow at 5pm (ACTIVE, MEDIUM)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
Need a meeting room for 8 people tomorrow 3-5pm at Corporate Office, internal review
```

Reply sent:

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_REQUIRED
- Subject: Information required: Meeting for 8 on tomorrow at 5pm [ROOM-2026-0001]

```
Dear Arjun Singh,

Thanks for your meeting-room request — it's registered as ROOM-2026-0001.

Here's what I have so far:

- Attendees: 8
- Date: tomorrow
- Start: 5pm
- Meeting type: internal meeting
- Location preference: Corporate Office

To lock in a room I just need:

- How long do you need the room (end time or duration)?

Also worth a quick check:

- Hybrid / AV: not answered
- Presentation display: not answered
- Catering / amenities: not answered
- Special access / security: not answered
- Confidentiality: not answered

Just reply to this email with the details.
```

### test_admin_desk_scenarios.py

27 cases, 0 failed.

#### test_hinglish_typos_become_a_facilities_ticket — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "ac". They wrote: "bhai 4th flr pe AC kaam nhi kr rha, bahut garmi h plz dekh lo"
2. The desk opened TKT-2026-0001 (AC not cooling on 4th floor) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to ops-desk@example.com. Subject: "Work Order: AC not cooling on 4th floor [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: AC not cooling on 4th floor Repair This item…"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: ac [TKT-2026-0001]". The message starts: "Hi Arjun, Noted - logged as TKT-2026-0001 and passed to Facilities. Workplace Team"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: AC not cooling on 4th floor (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: ac

```
bhai 4th flr pe AC kaam nhi kr rha, bahut garmi h plz dekh lo
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: AC not cooling on 4th floor [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: AC not cooling on 4th floor

Repair This item. Repairs on record: 0 of 6.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Air conditioning
Team: Facilities & Maintenance
Due by: 18 Oct, 7:46 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: 4th floor, near pantry
- Issue: AC not cooling

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the w…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: ac [TKT-2026-0001]

```
Hi Arjun,

Noted - logged as TKT-2026-0001 and passed to Facilities.

Workplace Team
```

#### test_pasted_back_questions_answer_the_open_case — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "visitor". They wrote: "a visitor coming, Neha Kapoor from Deloitte"
2. arjun.singh@acme.demo sent an email. Subject: "Re: visitor". They wrote: "Pls find the same - Which date and time is the visit? Thursday 8 Oct, 3 PM On Tue, Workplace Team wrote: > Which date and time is the visit?"
3. The desk opened VIS-2026-0001 (Visitor tomorrow) — completed.
4. It checked the records. Nothing in the records blocked it, so the desk carried on.
5. It wrote to arjun.singh@acme.demo. Subject: "Re: visitor [VIS-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged. Request: VIS-2026-0001 Subject: Visitor tomorrow Please reply with the following: - Which date and time is the …"
6. It wrote to ops-desk@example.com. Subject: "Done: Visitor tomorrow [VIS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: VIS-2026-0001 Subject: Visitor tomorrow Visitor pre-registered - add to today's gate manifest (No Securit…"
7. It wrote to arjun.singh@acme.demo. Subject: "Re: visitor [VIS-2026-0001]". The message starts: "Dear Arjun Singh, Your visitors have been pre-registered. Request: VIS-2026-0001 - Neha Kapoor: pass VP-470024 Please ask each visitor to carry a photo identit…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- VIS-2026-0001: Visitor tomorrow (ACTIVE, MEDIUM, stage COMPLETED, decision PROCEED)

Email received:

- From: arjun.singh@acme.demo
- Subject: visitor

```
a visitor coming, Neha Kapoor from Deloitte
```

- From: arjun.singh@acme.demo
- Subject: Re: visitor

```
Pls find the same

- Which date and time is the visit?  Thursday 8 Oct, 3 PM

On Tue, Workplace Team wrote:
> Which date and time is the visit?
```

Reply sent:

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: visitor [VIS-2026-0001]

```
Dear Arjun Singh,

Your request has been logged.

Request: VIS-2026-0001
Subject: Visitor tomorrow

Please reply with the following:
- Which date and time is the visit?

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Done: Visitor tomorrow [VIS-2026-0001]

```
Dear Team,

Please note the following update.

Request: VIS-2026-0001
Subject: Visitor tomorrow

Visitor pre-registered - add to today's gate manifest
(No Security & Front Desk contact set yet - sent to you. Add it in Company setup.)

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Visitor pre-registration
Team: Security & Front Desk
Due by: 18 Oct, 3:46 AM

Details:
- Visitor names: Neha Kapoor (Deloitte)
- Visit date: Thursday 8 Oct
- Time: 3 PM
- Pass VP-470024: Neha Kapoor (Deloitte)


Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: visitor [VIS-2026-0001]

```
Dear Arjun Singh,

Your visitors have been pre-registered.

Request: VIS-2026-0001
- Neha Kapoor: pass VP-470024
Please ask each visitor to carry a photo identity card and meet you at reception.

Regards,
Workplace Team
```

#### test_status_question_without_gemini_uses_case_state — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "printer". They wrote: "Printer on 2nd floor not working"
2. arjun.singh@acme.demo sent an email. Subject: "Re: printer". They wrote: "any update on this?"
3. The desk opened TKT-2026-0001 (Printer on 2nd floor not working) — handed to the team and still open.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
5. It wrote to ops-desk@example.com. Subject: "Work Order: Printer on 2nd floor not working [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Printer on 2nd floor not working Repair This…"
6. It wrote to arjun.singh@acme.demo. Subject: "Re: printer [TKT-2026-0001]". The message starts: "Hi Arjun, Thanks for letting us know. I've logged this as TKT-2026-0001 and passed it to the right team - we'll keep you posted here. Workplace Team"
7. It wrote to arjun.singh@acme.demo. Subject: "Re: printer [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Request: TKT-2026-0001 Subject: Printer on 2nd floor not working Status: dispatched Regards, Workplace Team"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Printer on 2nd floor not working (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: printer

```
Printer on 2nd floor not working
```

- From: arjun.singh@acme.demo
- Subject: Re: printer

```
any update on this?
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Printer on 2nd floor not working [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Printer on 2nd floor not working

Repair This item. Repairs on record: 0 of 6.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:46 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

What they asked: Printer on 2nd floor not working

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: printer [TKT-2026-0001]

```
Hi Arjun,

Thanks for letting us know. I've logged this as TKT-2026-0001 and passed it to the right team - we'll keep you posted here.

Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: printer [TKT-2026-0001]

```
Dear Arjun Singh,

Request: TKT-2026-0001
Subject: Printer on 2nd floor not working
Status: dispatched

Regards,
Workplace Team
```

#### test_auto_replies_and_no_reply_senders_are_not_answered — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Automatic reply: Your request". They wrote: "I am out of office till Monday."
2. no-reply@shop.example.com sent an email. Subject: "Order update". They wrote: "Your order has shipped"
3. arjun.singh@acme.demo sent an email. Subject: "Re: hi". They wrote: "Thanks for your mail"
4. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: arjun.singh@acme.demo
- Subject: Automatic reply: Your request

```
I am out of office till Monday.
```

- From: no-reply@shop.example.com
- Subject: Order update

```
Your order has shipped
```

- From: arjun.singh@acme.demo
- Subject: Re: hi

```
Thanks for your mail
```

#### test_supplies_within_limit_go_ahead_above_limit_need_approval — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "need 10 notebooks and 20 pens for the team, approx Rs 1800"
2. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "please order 6 ergonomic chairs, quote is INR 54,000"
3. The desk opened SUP-2026-0001 (Notebooks and pens) — handed to the team and still open; SUP-2026-0002 (Ergonomic chairs) — waiting for approval.
4. It checked the records. Nothing in the records blocked it, so the desk carried on.
5. It wrote to ops-desk@example.com. Subject: "Work Order: Notebooks and pens [SUP-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: SUP-2026-0001 Subject: Notebooks and pens New work order (No Admin …"
6. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [SUP-2026-0001]". The message starts: "Dear Arjun Singh, We have logged your request and assigned it to Admin & Workplace. Request: SUP-2026-0001 Subject: Notebooks and pens Status: Open You will be…"
7. It wrote to ops-desk@example.com. Subject: "Ops Decision: Ergonomic chairs [SUP-2026-0002]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: SUP-2026-0002 Subject: Ergonomic chairs Needs your approval - spend of INR 54,000 is…"
8. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [SUP-2026-0002]". The message starts: "Dear Arjun Singh, Your request has been logged and sent for approval. Request: SUP-2026-0002 Subject: Ergonomic chairs You will be updated on this thread once …"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- SUP-2026-0001: Notebooks and pens (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)
- SUP-2026-0002: Ergonomic chairs (ACTIVE, MEDIUM, stage AWAITING_APPROVAL, decision PROCEED)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
need 10 notebooks and 20 pens for the team, approx Rs 1800
```

- From: arjun.singh@acme.demo
- Subject: Request

```
please order 6 ergonomic chairs, quote is INR 54,000
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Notebooks and pens [SUP-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: SUP-2026-0001
Subject: Notebooks and pens

New work order
(No Admin & Workplace contact set yet - sent to you. Add it in Company setup.)

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Office supplies
Team: Admin & Workplace
Due by: 18 Oct, 11:46 PM

Details:
- Items: 10 notebooks, 20 pens
- Amount: 1800

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was delivered and to whom>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
When the item is ready, state where and from whom to collect i…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [SUP-2026-0001]

```
Dear Arjun Singh,

We have logged your request and assigned it to Admin & Workplace.

Request: SUP-2026-0001
Subject: Notebooks and pens
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Ergonomic chairs [SUP-2026-0002]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: SUP-2026-0002
Subject: Ergonomic chairs

Needs your approval - spend of INR 54,000 is above the auto-approve limit

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Office supplies
Team: Admin & Workplace

Details:
- Items: 6 ergonomic chairs
- Amount: 54000

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [SUP-2026-0002]

```
Dear Arjun Singh,

Your request has been logged and sent for approval.

Request: SUP-2026-0002
Subject: Ergonomic chairs

You will be updated on this thread once a decision is recorded.

Regards,
Workplace Team
```

#### test_onboarding_fans_out_and_sends_day_one_note — PASSED

What happened:

1. hr.lead@acme.demo sent an email. Subject: "Request". They wrote: "Sneha Iyer joins on 12 Oct in Gurugram, pls arrange everything"
2. The desk opened ONB-2026-0001 (Onboarding - Sneha Iyer) — handed to the team and still open.
3. It checked the records. Nothing in the records blocked it, so the desk carried on.
4. It wrote to ops-desk@example.com. Subject: "Work Order: Onboarding - Sneha Iyer [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding - Sneha Iyer New joiner onboardin…"
5. It wrote to it-helpdesk@acme-real.com. Subject: "Work Order: Onboarding - Sneha Iyer [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding - Sneha Iyer New joiner onboardin…"
6. It wrote to hr.lead@acme.demo. Subject: "Re: Request [ONB-2026-0001]". The message starts: "Dear Hr Lead, We have logged your request and assigned it to People / HR, Facilities & Maintenance, IT Support. Request: ONB-2026-0001 Subject: Onboarding - Sn…"
7. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ONB-2026-0001: Onboarding - Sneha Iyer (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: hr.lead@acme.demo
- Subject: Request

```
Sneha Iyer joins on 12 Oct in Gurugram, pls arrange everything
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding - Sneha Iyer [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding - Sneha Iyer

New joiner onboarding - People / HR + Facilities & Maintenance tasks
(No People / HR contact set yet - sent to you. Add it in Company setup.)

Tasks assigned:
1. Complete joining formalities, documents and induction for Sneha Iyer
2. Desk / workstation ready for Sneha Iyer by Monday 12 Oct

Requester: Hr Lead <hr.lead@acme.demo>
Type: New joiner onboarding
Teams working on it: People / HR + Facilities & Maintenance, IT Support
Due by: 18 Oct, 11:46 PM

Details:
- Employee name: Sneha Iyer
- Joining date: Monday 12 Oct
- Location: Corporate Office Gurugram

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete,…
```

- To: it-helpdesk@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding - Sneha Iyer [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding - Sneha Iyer

New joiner onboarding - IT Support tasks

Tasks assigned:
1. Laptop, company email ID and system logins ready for Sneha Iyer by Monday 12 Oct
2. Issue ID and access card for Sneha Iyer

Requester: Hr Lead <hr.lead@acme.demo>
Type: New joiner onboarding
Teams working on it: People / HR + Facilities & Maintenance, IT Support
Due by: 18 Oct, 11:46 PM

Details:
- Employee name: Sneha Iyer
- Joining date: Monday 12 Oct
- Location: Corporate Office Gurugram

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change…
```

- To: hr.lead@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [ONB-2026-0001]

```
Dear Hr Lead,

We have logged your request and assigned it to People / HR, Facilities & Maintenance, IT Support.

Request: ONB-2026-0001
Subject: Onboarding - Sneha Iyer
Status: Open

You will be updated on this thread when the work is complete.

First-days note for Sneha Iyer (you can forward this):
- Joined on Monday 12 Oct at Corporate Office Gurugram; HR will complete any pending joining formalities.
- The laptop, login, desk and ID / access card are being arranged; until the card is ready, please use a visitor pass at reception.

Regards,
Workplace Team
```

#### test_each_team_gets_only_its_own_tasks_and_the_raising_team_gets_none — PASSED

What happened:

1. hr.lead@acme-real.com sent an email. Subject: "New Joining - Priya Sharma". They wrote: "Hi Admin team, Please note that Priya Sharma has joined us today. Details: - Name: Priya Sharma - Employee ID: EMP-2041 - Location: 3rd floor, Bengaluru office…"
2. it-helpdesk@acme-real.com sent an email. Subject: "Re: Work Order: Onboarding for Priya Sharma [ONB-2026-0001]". They wrote: "on it, laptop being imaged"
3. it-helpdesk@acme-real.com sent an email. Subject: "Re: Work Order: Onboarding for Priya Sharma [ONB-2026-0001]". They wrote: "done, laptop and email handed over"
4. facilities@acme-real.com sent an email. Subject: "Re: Work Order: Onboarding for Priya Sharma [ONB-2026-0001]". They wrote: "done, desk 3F-12 allocated"
5. The desk opened ONB-2026-0001 (Onboarding for Priya Sharma) — closed as done.
6. It checked the records. Nothing in the records blocked it, so the desk carried on.
7. It wrote to it-helpdesk@acme-real.com. Subject: "Work Order: Onboarding for Priya Sharma [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding for Priya Sharma New joiner onboa…"
8. It wrote to facilities@acme-real.com. Subject: "Work Order: Onboarding for Priya Sharma [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding for Priya Sharma New joiner onboa…"
9. It wrote to hr.lead@acme-real.com. Subject: "Re: New Joining - Priya Sharma [ONB-2026-0001]". The message starts: "Dear Hr Lead, We have logged your request and assigned it to IT Support, Facilities & Maintenance. Request: ONB-2026-0001 Subject: Onboarding for Priya Sharma …"
10. It wrote to hr.lead@acme-real.com. Subject: "New Joining - Priya Sharma [ONB-2026-0001]". The message starts: "Dear Hr Lead, Update on ONB-2026-0001 (Onboarding for Priya Sharma) from IT Support: on it, laptop being imaged Regards, Workplace Team"
11. It wrote to ops-desk@example.com. Subject: "Ops Update: Onboarding for Priya Sharma [ONB-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ONB-2026-0001 Subject: Onboarding for Priya Sharma IT Support update: on it, laptop being imaged Requeste…"
12. It wrote to hr.lead@acme-real.com. Subject: "New Joining - Priya Sharma [ONB-2026-0001]". The message starts: "Dear Hr Lead, Progress on ONB-2026-0001 (Onboarding for Priya Sharma): IT Support has finished their part. - Set up Windows laptop with marketing software - Cr…"
13. It wrote to ops-desk@example.com. Subject: "Ops Update: Onboarding for Priya Sharma [ONB-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ONB-2026-0001 Subject: Onboarding for Priya Sharma IT Support done - still waiting on Facilities & Mainte…"
14. It wrote to hr.lead@acme-real.com. Subject: "New Joining - Priya Sharma [ONB-2026-0001]". The message starts: "Dear Hr Lead, Good news - ONB-2026-0001 (Onboarding for Priya Sharma) has been taken care of. Note from Facilities & Maintenance: desk 3F-12 allocated If anyth…"
15. It wrote to ops-desk@example.com. Subject: "Ops Update: Onboarding for Priya Sharma [ONB-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ONB-2026-0001 Subject: Onboarding for Priya Sharma Completed - Facilities & Maintenance finished the last…"
16. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ONB-2026-0001: Onboarding for Priya Sharma (RESOLVED, HIGH, stage RESOLVED, decision PROCEED)

Email received:

- From: hr.lead@acme-real.com
- Subject: New Joining - Priya Sharma

```
Hi Admin team,

Please note that Priya Sharma has joined us today.

Details:
- Name: Priya Sharma
- Employee ID: EMP-2041
- Location: 3rd floor, Bengaluru office

Could you please arrange the following:
1. Laptop, company email ID and system access
2. A desk/workstation near the marketing team
3. ID and access card for the office and 3rd floor

Thanks,
HR Team
```

- From: it-helpdesk@acme-real.com
- Subject: Re: Work Order: Onboarding for Priya Sharma [ONB-2026-0001]

```
on it, laptop being imaged
```

- From: it-helpdesk@acme-real.com
- Subject: Re: Work Order: Onboarding for Priya Sharma [ONB-2026-0001]

```
done, laptop and email handed over
```

- From: facilities@acme-real.com
- Subject: Re: Work Order: Onboarding for Priya Sharma [ONB-2026-0001]

```
done, desk 3F-12 allocated
```

Reply sent:

- To: it-helpdesk@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding for Priya Sharma [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding for Priya Sharma

New joiner onboarding - IT Support tasks

Tasks assigned:
1. Set up Windows laptop with marketing software
2. Create company email ID
3. Issue ID and access card for office and 3rd floor

Requester: Hr Lead <hr.lead@acme-real.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Priya Sharma
- Joining date: 2026-10-01
- Location: 3rd floor, Bengaluru

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- …
```

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding for Priya Sharma [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding for Priya Sharma

New joiner onboarding - Facilities & Maintenance tasks

Tasks assigned:
1. Allocate desk near the Marketing team, 3rd floor

Requester: Hr Lead <hr.lead@acme-real.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Priya Sharma
- Joining date: 2026-10-01
- Location: 3rd floor, Bengaluru

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "clo…
```

- To: hr.lead@acme-real.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: New Joining - Priya Sharma [ONB-2026-0001]

```
Dear Hr Lead,

We have logged your request and assigned it to IT Support, Facilities & Maintenance.

Request: ONB-2026-0001
Subject: Onboarding for Priya Sharma
Status: Open

You will be updated on this thread when the work is complete.

First-days note for Priya Sharma (you can forward this):
- Joined on 2026-10-01 at 3rd floor, Bengaluru; HR will complete any pending joining formalities.
- The laptop, login, desk and ID / access card are being arranged; until the card is ready, please use a visitor pass at reception.

Regards,
Workplace Team
```

- To: hr.lead@acme-real.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: New Joining - Priya Sharma [ONB-2026-0001]

```
Dear Hr Lead,

Update on ONB-2026-0001 (Onboarding for Priya Sharma) from IT Support: on it, laptop being imaged

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Onboarding for Priya Sharma [ONB-2026-0001]

```
Dear Team,

Please note the following update.

Request: ONB-2026-0001
Subject: Onboarding for Priya Sharma

IT Support update: on it, laptop being imaged

Requester: Hr Lead <hr.lead@acme-real.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Priya Sharma
- Joining date: 2026-10-01
- Location: 3rd floor, Bengaluru


Regards,
Workplace Team
```

- To: hr.lead@acme-real.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: New Joining - Priya Sharma [ONB-2026-0001]

```
Dear Hr Lead,

Progress on ONB-2026-0001 (Onboarding for Priya Sharma): IT Support has finished their part.
- Set up Windows laptop with marketing software
- Create company email ID
- Issue ID and access card for office and 3rd floor
Note from the team: laptop and email handed over

Still in progress: Facilities & Maintenance.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Onboarding for Priya Sharma [ONB-2026-0001]

```
Dear Team,

Please note the following update.

Request: ONB-2026-0001
Subject: Onboarding for Priya Sharma

IT Support done - still waiting on Facilities & Maintenance (laptop and email handed over)

Requester: Hr Lead <hr.lead@acme-real.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Priya Sharma
- Joining date: 2026-10-01
- Location: 3rd floor, Bengaluru


Regards,
Workplace Team
```

- To: hr.lead@acme-real.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: New Joining - Priya Sharma [ONB-2026-0001]

```
Dear Hr Lead,

Good news - ONB-2026-0001 (Onboarding for Priya Sharma) has been taken care of.
Note from Facilities & Maintenance: desk 3F-12 allocated

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Onboarding for Priya Sharma [ONB-2026-0001]

```
Dear Team,

Please note the following update.

Request: ONB-2026-0001
Subject: Onboarding for Priya Sharma

Completed - Facilities & Maintenance finished the last part: desk 3F-12 allocated

Requester: Hr Lead <hr.lead@acme-real.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Priya Sharma
- Joining date: 2026-10-01
- Location: 3rd floor, Bengaluru


Regards,
Workplace Team
```

#### test_admin_standing_in_for_a_team_only_finishes_that_team — PASSED

What happened:

1. hr.lead@acme-real.com sent an email. Subject: "New Joining - Naman". They wrote: "Hi Admin team, Please note that Priya Sharma has joined us today. Details: - Name: Priya Sharma - Employee ID: EMP-2041 - Location: 3rd floor, Bengaluru office…"
2. ops-desk@example.com sent an email. Subject: "Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". They wrote: "i have arranged everything, will hand over when he arrives"
3. ops-desk@example.com sent an email. Subject: "Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". They wrote: "i have arranged everything again"
4. facilities@acme-real.com sent an email. Subject: "Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". They wrote: "desk is ready"
5. The desk opened ONB-2026-0001 (Onboarding for Naman Kumar) — closed as done.
6. It checked the records. Nothing in the records blocked it, so the desk carried on.
7. It wrote to ops-desk@example.com. Subject: "Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar New joiner onboar…"
8. It wrote to facilities@acme-real.com. Subject: "Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar New joiner onboar…"
9. It wrote to hr.lead@acme-real.com. Subject: "Re: New Joining - Naman [ONB-2026-0001]". The message starts: "Dear Hr Lead, We have logged your request and assigned it to IT Support, Facilities & Maintenance. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar S…"
10. It wrote to hr.lead@acme-real.com. Subject: "New Joining - Naman [ONB-2026-0001]". The message starts: "Dear Hr Lead, Progress on ONB-2026-0001 (Onboarding for Naman Kumar): IT Support has finished their part. - Laptop, company email ID and system access - ID and…"
11. It wrote to hr.lead@acme-real.com. Subject: "New Joining - Naman [ONB-2026-0001]". The message starts: "Dear Hr Lead, Good news - ONB-2026-0001 (Onboarding for Naman Kumar) has been taken care of. Note from Facilities & Maintenance: desk is ready If anything is s…"
12. It wrote to ops-desk@example.com. Subject: "Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar Completed - Facilities & Maintenance finished the last …"
13. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ONB-2026-0001: Onboarding for Naman Kumar (RESOLVED, HIGH, stage RESOLVED, decision PROCEED)

Email received:

- From: hr.lead@acme-real.com
- Subject: New Joining - Naman

```
Hi Admin team,

Please note that Priya Sharma has joined us today.

Details:
- Name: Priya Sharma
- Employee ID: EMP-2041
- Location: 3rd floor, Bengaluru office

Could you please arrange the following:
1. Laptop, company email ID and system access
2. A desk/workstation near the marketing team
3. ID and access card for the office and 3rd floor

Thanks,
HR Team
```

- From: ops-desk@example.com
- Subject: Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
i have arranged everything, will hand over when he arrives
```

- From: ops-desk@example.com
- Subject: Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
i have arranged everything again
```

- From: facilities@acme-real.com
- Subject: Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
desk is ready
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

New joiner onboarding - IT Support tasks
(No IT Support contact set yet - sent to you. Add it in Company setup.)

Tasks assigned:
1. Laptop, company email ID and system access
2. ID and access card for the office and 3rd floor

Requester: Hr Lead <hr.lead@acme-real.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Naman Kumar
- Joining date: 2026-10-02

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work ord…
```

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

New joiner onboarding - Facilities & Maintenance tasks

Tasks assigned:
1. A desk/workstation near the marketing team

Requester: Hr Lead <hr.lead@acme-real.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Naman Kumar
- Joining date: 2026-10-02

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
If the team, type, or pr…
```

- To: hr.lead@acme-real.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: New Joining - Naman [ONB-2026-0001]

```
Dear Hr Lead,

We have logged your request and assigned it to IT Support, Facilities & Maintenance.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar
Status: Open

You will be updated on this thread when the work is complete.

First-days note for Naman Kumar (you can forward this):
- Joined on 2026-10-02 at the office reception; HR will complete any pending joining formalities.
- The laptop, login, desk and ID / access card are being arranged; until the card is ready, please use a visitor pass at reception.

Regards,
Workplace Team
```

- To: hr.lead@acme-real.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: New Joining - Naman [ONB-2026-0001]

```
Dear Hr Lead,

Progress on ONB-2026-0001 (Onboarding for Naman Kumar): IT Support has finished their part.
- Laptop, company email ID and system access
- ID and access card for the office and 3rd floor
Note from the team: i have arranged everything, will hand over when he arrives

Still in progress: Facilities & Maintenance.

Regards,
Workplace Team
```

- To: hr.lead@acme-real.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: New Joining - Naman [ONB-2026-0001]

```
Dear Hr Lead,

Good news - ONB-2026-0001 (Onboarding for Naman Kumar) has been taken care of.
Note from Facilities & Maintenance: desk is ready

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

Please note the following update.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

Completed - Facilities & Maintenance finished the last part: desk is ready

Requester: Hr Lead <hr.lead@acme-real.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Naman Kumar
- Joining date: 2026-10-02


Regards,
Workplace Team
```

#### test_team_replies_are_read_by_the_ai_not_keywords — PASSED

What happened:

1. hr.lead@acme-real.com sent an email. Subject: "New Joining - Naman". They wrote: "Hi Admin team, Please note that Priya Sharma has joined us today. Details: - Name: Priya Sharma - Employee ID: EMP-2041 - Location: 3rd floor, Bengaluru office…"
2. facilities@acme-real.com sent an email. Subject: "Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". They wrote: "the workstation is good to go, 3F-12"
3. it-helpdesk@acme-real.com sent an email. Subject: "Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". They wrote: "laptops are out of stock, vendor delivery friday"
4. The desk opened ONB-2026-0001 (Onboarding for Naman Kumar) — at_risk.
5. It checked the records. Nothing in the records blocked it, so the desk carried on.
6. It wrote to it-helpdesk@acme-real.com. Subject: "Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar New joiner onboar…"
7. It wrote to facilities@acme-real.com. Subject: "Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar New joiner onboar…"
8. It wrote to hr.lead@acme-real.com. Subject: "Re: New Joining - Naman [ONB-2026-0001]". The message starts: "Dear Hr Lead, We have logged your request and assigned it to IT Support, Facilities & Maintenance. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar S…"
9. It wrote to hr.lead@acme-real.com. Subject: "New Joining - Naman [ONB-2026-0001]". The message starts: "Dear Hr Lead, Progress on ONB-2026-0001 (Onboarding for Naman Kumar): Facilities & Maintenance has finished their part. - A desk/workstation near the marketing…"
10. It wrote to ops-desk@example.com. Subject: "Ops Update: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar Facilities & Maintenance done - still waiting on IT Sup…"
11. It wrote to ops-desk@example.com. Subject: "Ops Update: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, The following request is at risk of missing its due time. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar IT Support reports a problem: W…"
12. It wrote to hr.lead@acme-real.com. Subject: "New Joining - Naman [ONB-2026-0001]". The message starts: "Dear Hr Lead, A quick update on ONB-2026-0001 (Onboarding for Naman Kumar): IT Support has hit a snag - Waiting for laptop stock from the vendor We're on it an…"
13. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ONB-2026-0001: Onboarding for Naman Kumar (AT_RISK, HIGH, stage BLOCKED, decision PROCEED)

Email received:

- From: hr.lead@acme-real.com
- Subject: New Joining - Naman

```
Hi Admin team,

Please note that Priya Sharma has joined us today.

Details:
- Name: Priya Sharma
- Employee ID: EMP-2041
- Location: 3rd floor, Bengaluru office

Could you please arrange the following:
1. Laptop, company email ID and system access
2. A desk/workstation near the marketing team
3. ID and access card for the office and 3rd floor

Thanks,
HR Team
```

- From: facilities@acme-real.com
- Subject: Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
the workstation is good to go, 3F-12
```

- From: it-helpdesk@acme-real.com
- Subject: Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
laptops are out of stock, vendor delivery friday
```

Reply sent:

- To: it-helpdesk@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

New joiner onboarding - IT Support tasks

Tasks assigned:
1. Laptop, company email ID and system access
2. ID and access card for the office and 3rd floor

Requester: Hr Lead <hr.lead@acme-real.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Naman Kumar
- Joining date: 2026-10-02

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close",…
```

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

New joiner onboarding - Facilities & Maintenance tasks

Tasks assigned:
1. A desk/workstation near the marketing team

Requester: Hr Lead <hr.lead@acme-real.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Naman Kumar
- Joining date: 2026-10-02

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
If the team, type, or pr…
```

- To: hr.lead@acme-real.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: New Joining - Naman [ONB-2026-0001]

```
Dear Hr Lead,

We have logged your request and assigned it to IT Support, Facilities & Maintenance.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar
Status: Open

You will be updated on this thread when the work is complete.

First-days note for Naman Kumar (you can forward this):
- Joined on 2026-10-02 at the office reception; HR will complete any pending joining formalities.
- The laptop, login, desk and ID / access card are being arranged; until the card is ready, please use a visitor pass at reception.

Regards,
Workplace Team
```

- To: hr.lead@acme-real.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: New Joining - Naman [ONB-2026-0001]

```
Dear Hr Lead,

Progress on ONB-2026-0001 (Onboarding for Naman Kumar): Facilities & Maintenance has finished their part.
- A desk/workstation near the marketing team
Note from the team: Workstation 3F-12 is good to go

Still in progress: IT Support.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

Please note the following update.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

Facilities & Maintenance done - still waiting on IT Support (Workstation 3F-12 is good to go)

Requester: Hr Lead <hr.lead@acme-real.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Naman Kumar
- Joining date: 2026-10-02


Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Update: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

The following request is at risk of missing its due time.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

IT Support reports a problem: Waiting for laptop stock from the vendor

Requester: Hr Lead <hr.lead@acme-real.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Naman Kumar
- Joining date: 2026-10-02

Please reply "assign to <email>" to transfer it, "tell requester: <message>" to update the requester, "done - <note>" if it is already complete, or "cancel".

Regards,
Workplace Team
```

- To: hr.lead@acme-real.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: New Joining - Naman [ONB-2026-0001]

```
Dear Hr Lead,

A quick update on ONB-2026-0001 (Onboarding for Naman Kumar): IT Support has hit a snag - Waiting for laptop stock from the vendor

We're on it and will update you as soon as it moves.

Regards,
Workplace Team
```

#### test_done_phrasings — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_tasks_are_read_from_the_email_list_when_the_ai_gives_none — PASSED

What happened:

1. hr.lead@acme-real.com sent an email. Subject: "New Joining - Priya Sharma". They wrote: "Hi Admin team, Please note that Priya Sharma has joined us today. Details: - Name: Priya Sharma - Employee ID: EMP-2041 - Location: 3rd floor, Bengaluru office…"
2. The desk opened ONB-2026-0001 (Onboarding for Priya Sharma) — handed to the team and still open.
3. It checked the records. Nothing in the records blocked it, so the desk carried on.
4. It wrote to it-helpdesk@acme-real.com. Subject: "Work Order: Onboarding for Priya Sharma [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding for Priya Sharma New joiner onboa…"
5. It wrote to facilities@acme-real.com. Subject: "Work Order: Onboarding for Priya Sharma [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding for Priya Sharma New joiner onboa…"
6. It wrote to hr.lead@acme-real.com. Subject: "Re: New Joining - Priya Sharma [ONB-2026-0001]". The message starts: "Dear Hr Lead, We have logged your request and assigned it to IT Support, Facilities & Maintenance. Request: ONB-2026-0001 Subject: Onboarding for Priya Sharma …"
7. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ONB-2026-0001: Onboarding for Priya Sharma (ACTIVE, HIGH, stage DISPATCHED, decision PROCEED)

Email received:

- From: hr.lead@acme-real.com
- Subject: New Joining - Priya Sharma

```
Hi Admin team,

Please note that Priya Sharma has joined us today.

Details:
- Name: Priya Sharma
- Employee ID: EMP-2041
- Location: 3rd floor, Bengaluru office

Could you please arrange the following:
1. Laptop, company email ID and system access
2. A desk/workstation near the marketing team
3. ID and access card for the office and 3rd floor

Thanks,
HR Team
```

Reply sent:

- To: it-helpdesk@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding for Priya Sharma [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding for Priya Sharma

New joiner onboarding - IT Support tasks

Tasks assigned:
1. Laptop, company email ID and system access
2. ID and access card for the office and 3rd floor

Requester: Hr Lead <hr.lead@acme-real.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Priya Sharma
- Joining date: 2026-10-01
- Location: 3rd floor, Bengaluru

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "ch…
```

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding for Priya Sharma [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding for Priya Sharma

New joiner onboarding - Facilities & Maintenance tasks

Tasks assigned:
1. A desk/workstation near the marketing team

Requester: Hr Lead <hr.lead@acme-real.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Priya Sharma
- Joining date: 2026-10-01
- Location: 3rd floor, Bengaluru

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", o…
```

- To: hr.lead@acme-real.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: New Joining - Priya Sharma [ONB-2026-0001]

```
Dear Hr Lead,

We have logged your request and assigned it to IT Support, Facilities & Maintenance.

Request: ONB-2026-0001
Subject: Onboarding for Priya Sharma
Status: Open

You will be updated on this thread when the work is complete.

First-days note for Priya Sharma (you can forward this):
- Joined on 2026-10-01 at 3rd floor, Bengaluru; HR will complete any pending joining formalities.
- The laptop, login, desk and ID / access card are being arranged; until the card is ready, please use a visitor pass at reception.

Regards,
Workplace Team
```

#### test_name_given_in_the_email_is_never_asked_for_again — PASSED

What happened:

1. hr.lead@acme.demo sent an email. Subject: "New Joining - Priya Sharma". They wrote: "Hi Admin team, Please note that Priya Sharma has joined us today. Details: - Name: Priya Sharma - Joining date: 1 October 2026 - Employee ID: EMP-2041 - Locati…"
2. The desk opened ONB-2026-0001 (Onboarding logistics for Priya Sharma) — handed to the team and still open.
3. It checked the records. Nothing in the records blocked it, so the desk carried on.
4. It wrote to ops-desk@example.com. Subject: "Work Order: Onboarding logistics for Priya Sharma [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding logistics for Priya Sharma New jo…"
5. It wrote to it-helpdesk@acme-real.com. Subject: "Work Order: Onboarding logistics for Priya Sharma [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding logistics for Priya Sharma New jo…"
6. It wrote to hr.lead@acme.demo. Subject: "Re: New Joining - Priya Sharma [ONB-2026-0001]". The message starts: "Dear Hr Lead, We have logged your request and assigned it to People / HR, Facilities & Maintenance, IT Support. Request: ONB-2026-0001 Subject: Onboarding logi…"
7. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ONB-2026-0001: Onboarding logistics for Priya Sharma (ACTIVE, HIGH, stage DISPATCHED, decision PROCEED)

Email received:

- From: hr.lead@acme.demo
- Subject: New Joining - Priya Sharma

```
Hi Admin team,

Please note that Priya Sharma has joined us today.

Details:
- Name: Priya Sharma
- Joining date: 1 October 2026
- Employee ID: EMP-2041
- Location: 3rd floor, Bengaluru office

Could you please arrange the following:
1. Laptop, company email ID and system access
2. A desk/workstation near the marketing team
3. ID and access card for the office and 3rd floor

Thanks,
HR Team
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding logistics for Priya Sharma [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding logistics for Priya Sharma

New joiner onboarding - People / HR + Facilities & Maintenance tasks
(No People / HR contact set yet - sent to you. Add it in Company setup.)

Tasks assigned:
1. Complete joining formalities, documents and induction for Priya Sharma
2. A desk/workstation near the marketing team

Requester: Hr Lead <hr.lead@acme.demo>
Type: New joiner onboarding
Teams working on it: People / HR + Facilities & Maintenance, IT Support
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- On behalf of: Priya Sharma
- Employee id: EMP-2041
- Location: 3rd floor, Bengaluru
- Employee name: Priya Sharma
- Joining date: 1 October 2026

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the req…
```

- To: it-helpdesk@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding logistics for Priya Sharma [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding logistics for Priya Sharma

New joiner onboarding - IT Support tasks

Tasks assigned:
1. Laptop, company email ID and system access
2. ID and access card for the office and 3rd floor

Requester: Hr Lead <hr.lead@acme.demo>
Type: New joiner onboarding
Teams working on it: People / HR + Facilities & Maintenance, IT Support
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- On behalf of: Priya Sharma
- Employee id: EMP-2041
- Location: 3rd floor, Bengaluru
- Employee name: Priya Sharma
- Joining date: 1 October 2026

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "ass…
```

- To: hr.lead@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: New Joining - Priya Sharma [ONB-2026-0001]

```
Dear Hr Lead,

We have logged your request and assigned it to People / HR, Facilities & Maintenance, IT Support.

Request: ONB-2026-0001
Subject: Onboarding logistics for Priya Sharma
Status: Open

You will be updated on this thread when the work is complete.

First-days note for Priya Sharma (you can forward this):
- Joined on 1 October 2026 at 3rd floor, Bengaluru; HR will complete any pending joining formalities.
- The laptop, login, desk and ID / access card are being arranged; until the card is ready, please use a visitor pass at reception.

Regards,
Workplace Team
```

#### test_new_email_about_another_joiner_is_a_new_case_not_an_update — PASSED

What happened:

1. hr.lead@acme.demo sent an email. Subject: "New Joining - Priya". They wrote: "Priya Sharma joins, EMP-2041, please set up"
2. hr.lead@acme.demo sent an email. Subject: "New Joining - Amit Kumar". They wrote: "Details: - Name: Amit Kumar - Employee ID: EMP-2046 - Joining date: 1 Oct"
3. The desk opened ONB-2026-0001 (Onboarding for Priya Sharma) — waiting for the sender to reply with missing details; ONB-2026-0002 (New joiner onboarding) — handed to the team and still open.
4. It wrote to hr.lead@acme.demo. Subject: "Re: New Joining - Priya [ONB-2026-0001]". The message starts: "Dear Hr Lead, Your request has been logged. Request: ONB-2026-0001 Subject: Onboarding for Priya Sharma Please reply with the following: - What is their joinin…"
5. It wrote to ops-desk@example.com. Subject: "Work Order: New joiner onboarding [ONB-2026-0002]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0002 Subject: New joiner onboarding New joiner onboarding …"
6. It wrote to hr.lead@acme.demo. Subject: "Re: New Joining - Amit Kumar [ONB-2026-0002]". The message starts: "Dear Hr Lead, We have logged your request and assigned it to People / HR, IT Support, Facilities & Maintenance. Request: ONB-2026-0002 Subject: New joiner onbo…"
7. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ONB-2026-0001: Onboarding for Priya Sharma (ACTIVE, MEDIUM, stage AWAITING_INFO)
- ONB-2026-0002: New joiner onboarding (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: hr.lead@acme.demo
- Subject: New Joining - Priya

```
Priya Sharma joins, EMP-2041, please set up
```

- From: hr.lead@acme.demo
- Subject: New Joining - Amit Kumar

```
Details:
- Name: Amit Kumar
- Employee ID: EMP-2046
- Joining date: 1 Oct
```

Reply sent:

- To: hr.lead@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: New Joining - Priya [ONB-2026-0001]

```
Dear Hr Lead,

Your request has been logged.

Request: ONB-2026-0001
Subject: Onboarding for Priya Sharma

Please reply with the following:
- What is their joining date?

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: New joiner onboarding [ONB-2026-0002]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0002
Subject: New joiner onboarding

New joiner onboarding - People / HR + IT Support + Facilities & Maintenance tasks
(No People / HR contact set yet - sent to you. Add it in Company setup.)

Tasks assigned:
1. Complete joining formalities, documents and induction for Amit Kumar
2. Laptop, company email ID and system logins ready for Amit Kumar by 2026-10-01
3. Desk / workstation ready for Amit Kumar by 2026-10-01
4. Issue ID and access card for Amit Kumar

Requester: Hr Lead <hr.lead@acme.demo>
Type: New joiner onboarding
Teams working on it: People / HR + IT Support + Facilities & Maintenance
Due by: 18 Oct, 11:46 PM

Details:
- Employee name: Amit Kumar
- Employee id: EMP-2046
- Joining date: 2026-10-01

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" …
```

- To: hr.lead@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: New Joining - Amit Kumar [ONB-2026-0002]

```
Dear Hr Lead,

We have logged your request and assigned it to People / HR, IT Support, Facilities & Maintenance.

Request: ONB-2026-0002
Subject: New joiner onboarding
Status: Open

You will be updated on this thread when the work is complete.

First-days note for Amit Kumar (you can forward this):
- Joined on 2026-10-01 at the office reception; HR will complete any pending joining formalities.
- The laptop, login, desk and ID / access card are being arranged; until the card is ready, please use a visitor pass at reception.

Regards,
Workplace Team
```

#### test_reply_in_the_case_thread_still_updates_it — PASSED

What happened:

1. hr.lead@acme.demo sent an email. Subject: "Request". They wrote: "new joiner EMP-2041, please set up"
2. hr.lead@acme.demo sent an email. Subject: "Request". They wrote: "Her name is Priya Sharma, joining 1 Oct"
3. The desk opened ONB-2026-0001 (Onboarding) — handed to the team and still open.
4. It checked the records. Nothing in the records blocked it, so the desk carried on.
5. It wrote to hr.lead@acme.demo. Subject: "Re: Request [ONB-2026-0001]". The message starts: "Dear Hr Lead, Your request has been logged. Request: ONB-2026-0001 Subject: Onboarding Please reply with the following: - What is the new joiner's name? - What…"
6. It wrote to ops-desk@example.com. Subject: "Work Order: Onboarding [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding New joiner onboarding - People / …"
7. It wrote to hr.lead@acme.demo. Subject: "Re: Request [ONB-2026-0001]". The message starts: "Dear Hr Lead, We have logged your request and assigned it to People / HR, IT Support, Facilities & Maintenance. Request: ONB-2026-0001 Subject: Onboarding Stat…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ONB-2026-0001: Onboarding (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: hr.lead@acme.demo
- Subject: Request

```
new joiner EMP-2041, please set up
```

- From: hr.lead@acme.demo
- Subject: Request

```
Her name is Priya Sharma, joining 1 Oct
```

Reply sent:

- To: hr.lead@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [ONB-2026-0001]

```
Dear Hr Lead,

Your request has been logged.

Request: ONB-2026-0001
Subject: Onboarding

Please reply with the following:
- What is the new joiner's name?
- What is their joining date?

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding

New joiner onboarding - People / HR + IT Support + Facilities & Maintenance tasks
(No People / HR contact set yet - sent to you. Add it in Company setup.)

Tasks assigned:
1. Complete joining formalities, documents and induction for Priya Sharma
2. Laptop, company email ID and system logins ready for Priya Sharma by 2026-10-01
3. Desk / workstation ready for Priya Sharma by 2026-10-01
4. Issue ID and access card for Priya Sharma

Requester: Hr Lead <hr.lead@acme.demo>
Type: New joiner onboarding
Teams working on it: People / HR + IT Support + Facilities & Maintenance
Due by: 18 Oct, 11:46 PM

Details:
- Employee id: EMP-2041
- Employee name: Priya Sharma
- Joining date: 2026-10-01

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" t…
```

- To: hr.lead@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [ONB-2026-0001]

```
Dear Hr Lead,

We have logged your request and assigned it to People / HR, IT Support, Facilities & Maintenance.

Request: ONB-2026-0001
Subject: Onboarding
Status: Open

You will be updated on this thread when the work is complete.

First-days note for Priya Sharma (you can forward this):
- Joined on 2026-10-01 at the office reception; HR will complete any pending joining formalities.
- The laptop, login, desk and ID / access card are being arranged; until the card is ready, please use a visitor pass at reception.

Regards,
Workplace Team
```

#### test_fill_required_reads_label_lines — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_split_tasks_defaults_and_unmatched — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_onboarding_for_someone_who_already_joined_skips_report_on_wording — PASSED

What happened:

1. hr.lead@acme.demo sent an email. Subject: "Request". They wrote: "Priya Sharma joined today, please set her up"
2. The desk opened ONB-2026-0001 (Onboarding for Priya Sharma) — handed to the team and still open.
3. It checked the records. Nothing in the records blocked it, so the desk carried on.
4. It wrote to ops-desk@example.com. Subject: "Work Order: Onboarding for Priya Sharma [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding for Priya Sharma New joiner onboa…"
5. It wrote to hr.lead@acme.demo. Subject: "Re: Request [ONB-2026-0001]". The message starts: "Dear Hr Lead, We have logged your request and assigned it to People / HR, IT Support, Facilities & Maintenance. Request: ONB-2026-0001 Subject: Onboarding for …"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ONB-2026-0001: Onboarding for Priya Sharma (ACTIVE, HIGH, stage DISPATCHED, decision PROCEED)

Email received:

- From: hr.lead@acme.demo
- Subject: Request

```
Priya Sharma joined today, please set her up
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding for Priya Sharma [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding for Priya Sharma

New joiner onboarding - People / HR + IT Support + Facilities & Maintenance tasks
(No People / HR contact set yet - sent to you. Add it in Company setup.)

Tasks assigned:
1. Complete joining formalities, documents and induction for Priya Sharma
2. Laptop, company email ID and system logins ready for Priya Sharma by 2020-01-15
3. Desk / workstation ready for Priya Sharma by 2020-01-15
4. Issue ID and access card for Priya Sharma

Requester: Hr Lead <hr.lead@acme.demo>
Type: New joiner onboarding
Teams working on it: People / HR + IT Support + Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:46 AM

Details:
- Employee name: Priya Sharma
- Joining date: 2020-01-15
- Location: Bengaluru office

Please repl…
```

- To: hr.lead@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [ONB-2026-0001]

```
Dear Hr Lead,

We have logged your request and assigned it to People / HR, IT Support, Facilities & Maintenance.

Request: ONB-2026-0001
Subject: Onboarding for Priya Sharma
Status: Open

You will be updated on this thread when the work is complete.

First-days note for Priya Sharma (you can forward this):
- Joined on 2020-01-15 at Bengaluru office; HR will complete any pending joining formalities.
- The laptop, login, desk and ID / access card are being arranged; until the card is ready, please use a visitor pass at reception.

Regards,
Workplace Team
```

#### test_travel_asks_only_for_what_is_missing — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "need a cab to airport"
2. The desk opened TRV-2026-0001 (Cab to airport) — waiting for the sender to reply with missing details.
3. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [TRV-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged. Request: TRV-2026-0001 Subject: Cab to airport Please reply with the following: - When do you need to travel (d…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TRV-2026-0001: Cab to airport (ACTIVE, MEDIUM, stage AWAITING_INFO)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
need a cab to airport
```

Reply sent:

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [TRV-2026-0001]

```
Dear Arjun Singh,

Your request has been logged.

Request: TRV-2026-0001
Subject: Cab to airport

Please reply with the following:
- When do you need to travel (date and time)?

Regards,
Workplace Team
```

#### test_unknown_work_with_no_team_goes_to_admin — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "can admin organise the diwali party for 80 ppl"
2. The desk opened TKT-2026-0001 (Diwali party for 80 people) — waiting for approval.
3. It checked the records. Nothing in the records blocked it, so the desk carried on.
4. It wrote to ops-desk@example.com. Subject: "Ops Decision: Diwali party for 80 people [TKT-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: TKT-2026-0001 Subject: Diwali party for 80 people Needs your approval - no team is s…"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged and sent for approval. Request: TKT-2026-0001 Subject: Diwali party for 80 people You will be updated on this th…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Diwali party for 80 people (ACTIVE, MEDIUM, stage AWAITING_APPROVAL, decision PROCEED)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
can admin organise the diwali party for 80 ppl
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Diwali party for 80 people [TKT-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: TKT-2026-0001
Subject: Diwali party for 80 people

Needs your approval - no team is set up for event planning requests yet

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Event planning
Team: Admin & Workplace

Details:
- Headcount: 80

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged and sent for approval.

Request: TKT-2026-0001
Subject: Diwali party for 80 people

You will be updated on this thread once a decision is recorded.

Regards,
Workplace Team
```

#### test_ungrounded_draft_is_replaced_by_the_truth — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "pantry drain blocked"
2. The desk opened TKT-2026-0001 (Blocked drain) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 6 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
4. It wrote to ops-desk@example.com. Subject: "Work Order: Blocked drain [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Blocked drain Repair. No asset record matche…"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Blocked drain (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR_UNKNOWN)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
pantry drain blocked
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Blocked drain [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Blocked drain

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Plumbing
Team: Facilities & Maintenance
Due by: 18 Oct, 7:46 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: pantry

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if t…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

#### test_question_is_answered_without_opening_a_case — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "whats the wifi pwd for guests?"
2. It wrote to arjun.singh@acme.demo. Subject: "Re: Request". The message starts: "Hi Arjun, The guest Wi-Fi details are at reception. Workplace Team"
3. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
whats the wifi pwd for guests?
```

Reply sent:

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request

```
Hi Arjun,

The guest Wi-Fi details are at reception.

Workplace Team
```

#### test_admin_can_change_details_and_close_any_case — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "fan". They wrote: "Fan not working in cabin 12"
2. ops-desk@example.com sent an email. Subject: "Re: Work Order: Fan not working in cabin 12 [TKT-2026-0001]". They wrote: "change visit slot to Friday 4 PM"
3. ops-desk@example.com sent an email. Subject: "Re: Work Order: Fan not working in cabin 12 [TKT-2026-0001]". They wrote: "close"
4. The desk opened TKT-2026-0001 (Fan not working in cabin 12) — closed.
5. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
6. It wrote to ops-desk@example.com. Subject: "Work Order: Fan not working in cabin 12 [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Fan not working in cabin 12 Repair This item…"
7. It wrote to arjun.singh@acme.demo. Subject: "Re: fan [TKT-2026-0001]". The message starts: "Hi Arjun, Thanks for letting us know. I've logged this as TKT-2026-0001 and passed it to the right team - we'll keep you posted here. Workplace Team"
8. It wrote to arjun.singh@acme.demo. Subject: "fan [TKT-2026-0001]". The message starts: "Dear Arjun Singh, A quick update on TKT-2026-0001 (Fan not working in cabin 12): visit slot is now Friday 4 PM. Reply here if that doesn't work for you. Regard…"
9. It wrote to arjun.singh@acme.demo. Subject: "fan [TKT-2026-0001]". The message starts: "Dear Arjun Singh, TKT-2026-0001 (Fan not working in cabin 12) is now closed. Reply here if you need anything else. Regards, Workplace Team"
10. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Fan not working in cabin 12 (CLOSED, MEDIUM, stage CLOSED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: fan

```
Fan not working in cabin 12
```

- From: ops-desk@example.com
- Subject: Re: Work Order: Fan not working in cabin 12 [TKT-2026-0001]

```
change visit slot to Friday 4 PM
```

- From: ops-desk@example.com
- Subject: Re: Work Order: Fan not working in cabin 12 [TKT-2026-0001]

```
close
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Fan not working in cabin 12 [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Fan not working in cabin 12

Repair This item. Repairs on record: 0 of 6.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:46 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

What they asked: Fan not working in cabin 12

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done -…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: fan [TKT-2026-0001]

```
Hi Arjun,

Thanks for letting us know. I've logged this as TKT-2026-0001 and passed it to the right team - we'll keep you posted here.

Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: fan [TKT-2026-0001]

```
Dear Arjun Singh,

A quick update on TKT-2026-0001 (Fan not working in cabin 12): visit slot is now Friday 4 PM.

Reply here if that doesn't work for you.

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: fan [TKT-2026-0001]

```
Dear Arjun Singh,

TKT-2026-0001 (Fan not working in cabin 12) is now closed. Reply here if you need anything else.

Regards,
Workplace Team
```

#### test_digest_mode_batches_completion_notes — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "Karan Mehta from EY visiting Monday"
2. The desk opened VIS-2026-0001 (Visitor Monday) — completed.
3. It checked the records. Nothing in the records blocked it, so the desk carried on.
4. It wrote to frontdesk@acme-real.com. Subject: "Done: Visitor Monday [VIS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: VIS-2026-0001 Subject: Visitor Monday Visitor pre-registered - add to today's gate manifest Requester: Ar…"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [VIS-2026-0001]". The message starts: "Dear Arjun Singh, Your visitors have been pre-registered. Request: VIS-2026-0001 - Karan Mehta: pass VP-7744C7 Please ask each visitor to carry a photo identit…"
6. It wrote to ops-desk@example.com. Subject: "Daily operations summary — 17 Oct 2026". The message starts: "Dear Colleague, Daily operations summary — Saturday 17 October 2026 Completed since yesterday: 1 - VIS-2026-0001 Visitor Monday - resolved (SECURITY, arjun.sin…"
7. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- VIS-2026-0001: Visitor Monday (ACTIVE, MEDIUM, stage COMPLETED, decision PROCEED)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
Karan Mehta from EY visiting Monday
```

Reply sent:

- To: frontdesk@acme-real.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Done: Visitor Monday [VIS-2026-0001]

```
Dear Team,

Please note the following update.

Request: VIS-2026-0001
Subject: Visitor Monday

Visitor pre-registered - add to today's gate manifest

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Visitor pre-registration
Team: Security & Front Desk
Due by: 18 Oct, 3:46 AM

Details:
- Visitor names: Karan Mehta (EY)
- Visit date: Monday 12 Oct
- Pass VP-7744C7: Karan Mehta (EY)


Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [VIS-2026-0001]

```
Dear Arjun Singh,

Your visitors have been pre-registered.

Request: VIS-2026-0001
- Karan Mehta: pass VP-7744C7
Please ask each visitor to carry a photo identity card and meet you at reception.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Daily operations summary — 17 Oct 2026

```
Dear Colleague,

Daily operations summary — Saturday 17 October 2026

Completed since yesterday: 1
- VIS-2026-0001 Visitor Monday - resolved (SECURITY, arjun.singh@acme.demo)

Please reply on the request email if any item requires a decision.

Regards,
Workplace Team
```

#### test_demo_reset_clears_desk_tickets_and_passes — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_permanent_employee_parking_goes_to_security_without_a_date — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "hi". They wrote: "I need car parking"
2. arjun.singh@acme.demo sent an email. Subject: "Re: hi". They wrote: "Car No: DL2caz9103 I am new joinee and need permanent car parking"
3. The desk opened PRK-2026-0001 (Car parking allocation) — handed to the team and still open.
4. It checked the records. Nothing in the records blocked it, so the desk carried on.
5. It wrote to arjun.singh@acme.demo. Subject: "Re: hi [PRK-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged. Request: PRK-2026-0001 Subject: Car parking allocation Please reply with the following: - What is the vehicle n…"
6. It wrote to frontdesk@acme-real.com. Subject: "Work Order: Car parking allocation [PRK-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: PRK-2026-0001 Subject: Car parking allocation Employee parking - pe…"
7. It wrote to arjun.singh@acme.demo. Subject: "Re: hi [PRK-2026-0001]". The message starts: "Hi Kapil, Thanks! I've forwarded it to the Security team. Workplace Team"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- PRK-2026-0001: Car parking allocation (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: arjun.singh@acme.demo
- Subject: hi

```
I need car parking
```

- From: arjun.singh@acme.demo
- Subject: Re: hi

```
Car No: DL2caz9103

I am new joinee and need permanent car parking
```

Reply sent:

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: hi [PRK-2026-0001]

```
Dear Arjun Singh,

Your request has been logged.

Request: PRK-2026-0001
Subject: Car parking allocation

Please reply with the following:
- What is the vehicle number?
- Which date do you need parking?

Regards,
Workplace Team
```

- To: frontdesk@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Car parking allocation [PRK-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: PRK-2026-0001
Subject: Car parking allocation

Employee parking - permanent allocation needed

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Parking
Team: Security & Front Desk
Due by: 18 Oct, 3:47 AM

Details:
- Vehicle numbers: DL2caz9103
- Parking type: employee_permanent
- Visit date: Permanent

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
If the team, type, or priority is wrong, reply "change team to <team>", "change type to <type>", or "change priority to high".

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: hi [PRK-2026-0001]

```
Hi Kapil,

Thanks! I've forwarded it to the Security team.

Workplace Team
```

#### test_update_reply_claiming_forwarded_is_replaced_when_still_waiting — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "parking". They wrote: "need guest parking"
2. arjun.singh@acme.demo sent an email. Subject: "Re: parking". They wrote: "car HR26AB1234"
3. The desk opened PRK-2026-0001 (Guest parking) — waiting for the sender to reply with missing details.
4. It wrote to arjun.singh@acme.demo. Subject: "Re: parking [PRK-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged. Request: PRK-2026-0001 Subject: Guest parking Please reply with the following: - What is the vehicle number? - …"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: parking [PRK-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged. Request: PRK-2026-0001 Subject: Guest parking Please reply with the following: - Which date do you need parking…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- PRK-2026-0001: Guest parking (ACTIVE, MEDIUM, stage AWAITING_INFO)

Email received:

- From: arjun.singh@acme.demo
- Subject: parking

```
need guest parking
```

- From: arjun.singh@acme.demo
- Subject: Re: parking

```
car HR26AB1234
```

Reply sent:

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: parking [PRK-2026-0001]

```
Dear Arjun Singh,

Your request has been logged.

Request: PRK-2026-0001
Subject: Guest parking

Please reply with the following:
- What is the vehicle number?
- Which date do you need parking?

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: parking [PRK-2026-0001]

```
Dear Arjun Singh,

Your request has been logged.

Request: PRK-2026-0001
Subject: Guest parking

Please reply with the following:
- Which date do you need parking?

Regards,
Workplace Team
```

#### test_tool_catalogue_marks_room_and_invoice_as_existing_flows — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_admin_ops.py

6 cases, 0 failed.

#### test_admin_ops_email_reads_env — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_briefing_puts_special_requests_in_own_section — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_decision_briefing_uses_ops_decision_label — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_complete_fit_sends_structured_ops_update — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 4 on 22 September at 10 am (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 4 on 22 September at 10 am (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Focus Room 5A (seats 8) Your booking: - Attendees: 4 - Date: 22 Septemb…"
3. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 4 on 22 September at 10 am (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Focus Room 5A Case: ROOM-2026-0001 Hold window: 10 am (setup 30m earlier) – 10 am + 2.0h (+15m r…"
4. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Focus Room 5A [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Focus Room 5A Requester: employee1@acme.demo When: Tue 22 Sep 2026, 10 am · Corporate Offi…"
5. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 4 on 22 September at 10 am (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 4 on 22 September at 10 am (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Focus Room 5A (seats 8)

Your booking:
- Attendees: 4
- Date: 22 September
- Time: 10 am (2.0h)
- Meeting type: workshop
- Presentation display: yes
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: extra whiteboard markers
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 4 on 22 September at 10 am (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Focus Room 5A
Case: ROOM-2026-0001
Hold window: 10 am (setup 30m earlier) – 10 am + 2.0h (+15m release)

Active preparations: AV/display.
No separate approval is needed for meeting room, installed AV / VC and internal IT support, standard stationery and printing.
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Focus Room 5A [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Focus Room 5A

Requester: employee1@acme.demo
When: Tue 22 Sep 2026, 10 am · Corporate Office
Room: Focus Room 5A (8 seats), setup 30 min before
People: 4

To arrange:
- Display / screen
- Extra whiteboard markers
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Standard stationery and printing
    · Extra whiteboard markers
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Focus Room 5A after the meeting
- IT / AV: with you (no IT Support mailbox set yet)
    · Display / projector working
    · AV test done by 22 Sep, 9:30 AM
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action i…
```

#### test_no_resource_sends_ops_decision — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h)) — still open.
2. It wrote to big.team@company.com. Subject: "No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, No room fits 80 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40 o…"
3. It wrote to ops-desk@example.com. Subject: "Ops Decision: No suitable room in inventory [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: No suitable room in inventory No room fits 80 people in person (largest inventory room holds 40). Requester: b…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

No room fits 80 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: No suitable room in inventory [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: No suitable room in inventory
No room fits 80 people in person (largest inventory room holds 40).

Requester: big.team@company.com
When: Tue 22 Sep 2026, 2:00 PM–5:00 PM · Corporate Office
People: 80
Needs: display
Also asked: orchestrator role: module_helper
Room: none fits — No room fits 80 people in person (largest inventory room holds 40).

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

#### test_admin_notify_disabled_when_env_blank — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 4 on 22 September at 10 am (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 4 on 22 September at 10 am (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 4 - Date: 22 Sep…"
3. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 4 on 22 September at 10 am (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 4 on 22 September at 10 am (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 4
- Date: 22 September
- Time: 10 am (2.0h)
- Meeting type: workshop
- Location preference: Corporate Office
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Catering / amenities: none
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

### test_ai_learning.py

8 cases, 1 failed.

#### test_admin_can_fix_team_type_and_priority_and_it_is_recorded — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Projector not working". They wrote: "Projector not working"
2. ops-desk@example.com sent an email. Subject: "Re: Work Order: Projector not working [TKT-2026-0001]". They wrote: "change team to IT"
3. ops-desk@example.com sent an email. Subject: "Re: Work Order: Projector not working [TKT-2026-0001]". They wrote: "change priority to high"
4. ops-desk@example.com sent an email. Subject: "Re: Work Order: Projector not working [TKT-2026-0001]". They wrote: "change type to it_support"
5. The desk opened TKT-2026-0001 (Projector not working) — handed to the team and still open.
6. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
7. It wrote to ops-desk@example.com. Subject: "Work Order: Projector not working [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Projector not working Repair This item. Repa…"
8. It wrote to arjun.singh@acme.demo. Subject: "Re: Projector not working [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
9. It wrote to it-helpdesk@acme-real.com. Subject: "Work Order: Projector not working [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Projector not working Re-routed to you by op…"
10. It wrote to ops-desk@example.com. Subject: "Work Order: Projector not working [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Projector not working Moved to IT Support - no action needed from you. Record chec…"
11. It wrote to it-helpdesk@acme-real.com. Subject: "Work Order: Projector not working [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Projector not working Re-routed to you by op…"
12. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Projector not working (ACTIVE, HIGH, stage DISPATCHED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: Projector not working

```
Projector not working
```

- From: ops-desk@example.com
- Subject: Re: Work Order: Projector not working [TKT-2026-0001]

```
change team to IT
```

- From: ops-desk@example.com
- Subject: Re: Work Order: Projector not working [TKT-2026-0001]

```
change priority to high
```

- From: ops-desk@example.com
- Subject: Re: Work Order: Projector not working [TKT-2026-0001]

```
change type to it_support
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Projector not working [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Projector not working

Repair This item. Repairs on record: 0 of 6.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 7
- Issue: Projector not working

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Projector not working [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: it-helpdesk@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Projector not working [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Projector not working

Re-routed to you by ops-desk@example.com

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: IT Support
Due by: 18 Oct, 7:47 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 7
- Issue: Projector not working

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <email>" to transfer the work order…
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Work Order: Projector not working [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Projector not working

Moved to IT Support - no action needed from you.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: IT Support
Due by: 18 Oct, 7:47 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: cabin 7
- Issue: Projector not working


Regards,
Workplace Team
```

- To: it-helpdesk@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Projector not working [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Projector not working

Re-routed to you by ops-desk@example.com (now IT support)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: IT support
Team: IT Support
Priority: High (set by ops-desk@example.com)
Due by: 18 Oct, 7:47 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 7
- Issue: Projector not working

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag …
```

#### test_team_reply_follows_the_override — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Projector flickering". They wrote: "Projector flickering"
2. ops-desk@example.com sent an email. Subject: "Re: Work Order: Projector flickering [TKT-2026-0001]". They wrote: "change team to IT"
3. it-helpdesk@acme-real.com sent an email. Subject: "Re: Work Order: Projector flickering [TKT-2026-0001]". They wrote: "done, replaced the HDMI cable"
4. The desk opened TKT-2026-0001 (Projector flickering) — closed as done.
5. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
6. It wrote to ops-desk@example.com. Subject: "Work Order: Projector flickering [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Projector flickering Repair This item. Repai…"
7. It wrote to arjun.singh@acme.demo. Subject: "Re: Projector flickering [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
8. It wrote to it-helpdesk@acme-real.com. Subject: "Work Order: Projector flickering [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Projector flickering Re-routed to you by ops…"
9. It wrote to ops-desk@example.com. Subject: "Work Order: Projector flickering [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Projector flickering Moved to IT Support - no action needed from you. Record check…"
10. It wrote to arjun.singh@acme.demo. Subject: "Projector flickering [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Good news - TKT-2026-0001 (Projector flickering) has been taken care of. Note from IT Support: replaced the HDMI cable If anything is still n…"
11. It wrote to ops-desk@example.com. Subject: "Work Order: Projector flickering [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Projector flickering Completed by IT Support: replaced the HDMI cable Record check…"
12. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Projector flickering (RESOLVED, MEDIUM, stage RESOLVED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: Projector flickering

```
Projector flickering
```

- From: ops-desk@example.com
- Subject: Re: Work Order: Projector flickering [TKT-2026-0001]

```
change team to IT
```

- From: it-helpdesk@acme-real.com
- Subject: Re: Work Order: Projector flickering [TKT-2026-0001]

```
done, replaced the HDMI cable
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Projector flickering [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Projector flickering

Repair This item. Repairs on record: 0 of 6.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 7
- Issue: Projector flickering

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- …
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Projector flickering [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: it-helpdesk@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Projector flickering [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Projector flickering

Re-routed to you by ops-desk@example.com

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: IT Support
Due by: 18 Oct, 7:47 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 7
- Issue: Projector flickering

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <email>" to transfer the work order
-…
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Work Order: Projector flickering [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Projector flickering

Moved to IT Support - no action needed from you.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: IT Support
Due by: 18 Oct, 7:47 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: cabin 7
- Issue: Projector flickering


Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Projector flickering [TKT-2026-0001]

```
Dear Arjun Singh,

Good news - TKT-2026-0001 (Projector flickering) has been taken care of.
Note from IT Support: replaced the HDMI cable

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Work Order: Projector flickering [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Projector flickering

Completed by IT Support: replaced the HDMI cable

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: IT Support
Due by: 18 Oct, 7:47 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: cabin 7
- Issue: Projector flickering


Regards,
Workplace Team
```

#### test_admin_answer_becomes_a_draft_the_ai_only_uses_after_approval — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "what are the gym timings?"
2. ops-desk@example.com sent an email. Subject: "Re: Work Order: Question: Gym timings [TKT-2026-0001]". They wrote: "tell requester: the gym is open 7am to 10pm on weekdays"
3. The desk opened TKT-2026-0001 (Question: Gym timings) — closed as done.
4. It checked the records. Nothing in the records blocked it, so the desk carried on.
5. It wrote to ops-desk@example.com. Subject: "Work Order: Question: Gym timings [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Question: Gym timings Question needs a verif…"
6. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [TKT-2026-0001]". The message starts: "Dear Arjun Singh, A verified answer is not on record for that question. It has been referred to the administrator (TKT-2026-0001). The reply will come on this …"
7. It wrote to arjun.singh@acme.demo. Subject: "Request [TKT-2026-0001]". The message starts: "Dear Arjun Singh, About your question (TKT-2026-0001): the gym is open 7am to 10pm on weekdays Regards, Workplace Team"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Question: Gym timings (RESOLVED, MEDIUM, stage RESOLVED, decision PROCEED)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
what are the gym timings?
```

- From: ops-desk@example.com
- Subject: Re: Work Order: Question: Gym timings [TKT-2026-0001]

```
tell requester: the gym is open 7am to 10pm on weekdays
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Question: Gym timings [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Question: Gym timings

Question needs a verified answer - reply "tell requester: <answer>"
(No Admin & Workplace contact set yet - sent to you. Add it in Company setup.)

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: General admin request
Team: Admin & Workplace
Due by: 18 Oct, 11:47 PM

Details:
- Question: what are the gym timings?

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
If the team, type, or priority is wrong, reply "change team to <team>", "change type to <type>…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [TKT-2026-0001]

```
Dear Arjun Singh,

A verified answer is not on record for that question. It has been referred to the administrator (TKT-2026-0001). The reply will come on this thread.

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Request [TKT-2026-0001]

```
Dear Arjun Singh,

About your question (TKT-2026-0001): the gym is open 7am to 10pm on weekdays

Regards,
Workplace Team
```

#### test_repeated_rerouting_becomes_a_one_click_rule — FAILED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Projector issue 1". They wrote: "Projector issue 1"
2. ops-desk@example.com sent an email. Subject: "Re: Work Order: Projector issue 1 [TKT-2026-0001]". They wrote: "change team to IT"
3. arjun.singh@acme.demo sent an email. Subject: "Projector issue 2". They wrote: "Projector issue 2"
4. The desk opened TKT-2026-0001 (Projector issue 1) — handed to the team and still open; TKT-2026-0002 (Projector issue 2) — closed.
5. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
6. It wrote to ops-desk@example.com. Subject: "Work Order: Projector issue 1 [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Projector issue 1 Repair This item. Repairs …"
7. It wrote to arjun.singh@acme.demo. Subject: "Re: Projector issue 1 [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
8. It wrote to ops-desk@example.com. Subject: "Work Order: Projector issue 1 [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Projector issue 1 Re-routed to you by ops-de…"
9. It wrote to arjun.singh@acme.demo. Subject: "Re: Projector issue 2 [TKT-2026-0001]". The message starts: "Dear Arjun Singh, This report has been linked to open request TKT-2026-0001. The assigned team will continue on that request. Regards, Workplace Team"
10. Result: this test failed. The replies above were still written, and the failure is noted at the end of this case.


Case state:

- TKT-2026-0001: Projector issue 1 (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)
- TKT-2026-0002: Projector issue 2 (CLOSED, MEDIUM, stage LINKED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: Projector issue 1

```
Projector issue 1
```

- From: ops-desk@example.com
- Subject: Re: Work Order: Projector issue 1 [TKT-2026-0001]

```
change team to IT
```

- From: arjun.singh@acme.demo
- Subject: Projector issue 2

```
Projector issue 2
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Projector issue 1 [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Projector issue 1

Repair This item. Repairs on record: 0 of 6.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 7
- Issue: Projector issue 1

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done …
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Projector issue 1 [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Projector issue 1 [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Projector issue 1

Re-routed to you by ops-desk@example.com
(No IT Support contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: IT Support
Due by: 18 Oct, 7:47 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 7
- Issue: Projector issue 1

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a pho…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Projector issue 2 [TKT-2026-0001]

```
Dear Arjun Singh,

This report has been linked to open request TKT-2026-0001. The assigned team will continue on that request.

Regards,
Workplace Team
```

Failure:

```
E   IndexError: list index out of range
```

#### test_accuracy_reflects_human_corrections — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Fan noisy". They wrote: "Fan noisy"
2. arjun.singh@acme.demo sent an email. Subject: "Monitor broken". They wrote: "Monitor broken"
3. ops-desk@example.com sent an email. Subject: "Re: Work Order: Monitor broken [TKT-2026-0002]". They wrote: "change type to it_support"
4. The desk opened TKT-2026-0001 (Fan noisy) — handed to the team and still open; TKT-2026-0002 (Monitor broken) — handed to the team and still open.
5. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
6. It wrote to ops-desk@example.com. Subject: "Work Order: Fan noisy [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Fan noisy Repair This item. Repairs on recor…"
7. It wrote to arjun.singh@acme.demo. Subject: "Re: Fan noisy [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
8. It wrote to ops-desk@example.com. Subject: "Work Order: Monitor broken [TKT-2026-0002]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0002 Subject: Monitor broken Repair This item. Repairs on …"
9. It wrote to arjun.singh@acme.demo. Subject: "Re: Monitor broken [TKT-2026-0002]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
10. It wrote to ops-desk@example.com. Subject: "Work Order: Monitor broken [TKT-2026-0002]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0002 Subject: Monitor broken Re-routed to you by ops-desk@…"
11. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Fan noisy (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)
- TKT-2026-0002: Monitor broken (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: Fan noisy

```
Fan noisy
```

- From: arjun.singh@acme.demo
- Subject: Monitor broken

```
Monitor broken
```

- From: ops-desk@example.com
- Subject: Re: Work Order: Monitor broken [TKT-2026-0002]

```
change type to it_support
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Fan noisy [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Fan noisy

Repair This item. Repairs on record: 0 of 6.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 7
- Issue: Fan noisy

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixe…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Fan noisy [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Monitor broken [TKT-2026-0002]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0002
Subject: Monitor broken

Repair This item. Repairs on record: 0 of 6.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: CleanSupply Partners

Investigation:
Prior related work: Repair This item. Repairs on record: 0 of 6.; Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 7
- Issue: Monitor broken

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "is…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Monitor broken [TKT-2026-0002]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0002)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Monitor broken [TKT-2026-0002]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0002
Subject: Monitor broken

Re-routed to you by ops-desk@example.com (now IT support)
(No IT Support contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: IT support
Team: IT Support
Due by: 18 Oct, 7:47 AM
Preferred vendor: CleanSupply Partners

Investigation:
Prior related work: Repair This item. Repairs on record: 0 of 6.; Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 7
- Issue: Monitor broken

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is bl…
```

#### test_regression_check_runs_without_side_effects — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_regression_check_scores_the_model_answers — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_learning_endpoints — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_blueprint_controls.py

13 cases, 2 failed.

#### test_bare_done_asks_for_proof_and_proof_makes_closure_verified — FAILED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "chair". They wrote: "chair wheel broken in cabin 4"
2. The desk opened TKT-2026-0001 (Chair wheel broken) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 4 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair wheel broken [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Chair wheel broken Repair This item. Repairs…"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
6. Result: this test failed. The replies above were still written, and the failure is noted at the end of this case.


Case state:

- TKT-2026-0001: Chair wheel broken (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: chair

```
chair wheel broken in cabin 4
```

Reply sent:

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair wheel broken [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Chair wheel broken

Repair This item. Repairs on record: 0 of 4.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 4

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Furniture
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: BrightFurniture Co

Investigation:
Approved vendor on file: BrightFurniture Co; Route to Facilities & Maintenance

Details:
- Location: cabin 4
- Issue: chair wheel broken
- Item: chair wheel broken

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <e…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

Failure:

```
E   assert 'only marked verified' in 'Dear Team,\n\nA work order has been assigned to your team. The particulars are below.\n\nRequest: TKT-2026-0001\nSubj...g, reply "change team to <team>", "change type to <type>", or "change priority to high".\n\nRegards,\nWorkplace Team\n'
     +  where 'Dear Team,\n\nA work order has been assigned to your team. The particulars are below.\n\nRequest: TKT-2026-0001\nSubj...g, reply "change team to <team>", "change type to <type>", or "change priority to high…
```

#### test_no_evidence_closes_honestly_and_is_not_learned_from — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "chair". They wrote: "chair wheel broken in cabin 4"
2. facilities@acme-real.com sent an email. Subject: "Re: Work Order: Chair wheel broken [TKT-2026-0001]". They wrote: "done"
3. The desk opened TKT-2026-0001 (Chair wheel broken) — closed.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 4 repairs. The records did not call for a replacement, so this stayed a normal repair.
5. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair wheel broken [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Chair wheel broken Repair This item. Repairs…"
6. It wrote to arjun.singh@acme.demo. Subject: "Re: chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
7. It wrote to arjun.singh@acme.demo. Subject: "chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Good news - TKT-2026-0001 (Chair wheel broken) has been taken care of. If anything is still not right, just reply "not fixed" and I'll reopen…"
8. It wrote to ops-desk@example.com. Subject: "Ops Update: Chair wheel broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair wheel broken Completed by Facilities & Maintenance Record check: - Item: no …"
9. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair wheel broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair wheel broken Thanks for completing this. To close it as verified, please rep…"
10. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Chair wheel broken (CLOSED, MEDIUM, stage CLOSED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: chair

```
chair wheel broken in cabin 4
```

- From: facilities@acme-real.com
- Subject: Re: Work Order: Chair wheel broken [TKT-2026-0001]

```
done
```

Reply sent:

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair wheel broken [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Chair wheel broken

Repair This item. Repairs on record: 0 of 4.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 4

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Furniture
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: BrightFurniture Co

Investigation:
Approved vendor on file: BrightFurniture Co; Route to Facilities & Maintenance

Details:
- Location: cabin 4
- Issue: chair wheel broken
- Item: chair wheel broken

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <e…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Good news - TKT-2026-0001 (Chair wheel broken) has been taken care of.

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Chair wheel broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair wheel broken

Completed by Facilities & Maintenance

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 4

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Furniture
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: BrightFurniture Co

Details:
- Location: cabin 4
- Issue: chair wheel broken
- Item: chair wheel broken


Regards,
Workplace Team
```

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair wheel broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair wheel broken

Thanks for completing this. To close it as verified, please reply with what was fixed or done (a photo works too) (or attach a photo).

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 4

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Furniture
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: BrightFurniture Co

Details:
- Location: cabin 4
- Issue: chair wheel broken
- Item: chair wheel broken


Regards,
Workplace Team
```

#### test_photo_attachment_counts_as_evidence — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "chair". They wrote: "chair wheel broken in cabin 4"
2. The desk opened TKT-2026-0001 (Chair wheel broken) — closed as done.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 4 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair wheel broken [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Chair wheel broken Repair This item. Repairs…"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
6. It wrote to arjun.singh@acme.demo. Subject: "chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Good news - TKT-2026-0001 (Chair wheel broken) has been taken care of. If anything is still not right, just reply "not fixed" and I'll reopen…"
7. It wrote to ops-desk@example.com. Subject: "Ops Update: Chair wheel broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair wheel broken Completed by Facilities & Maintenance Record check: - Item: no …"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Chair wheel broken (RESOLVED, MEDIUM, stage RESOLVED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: chair

```
chair wheel broken in cabin 4
```

Reply sent:

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair wheel broken [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Chair wheel broken

Repair This item. Repairs on record: 0 of 4.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 4

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Furniture
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: BrightFurniture Co

Investigation:
Approved vendor on file: BrightFurniture Co; Route to Facilities & Maintenance

Details:
- Location: cabin 4
- Issue: chair wheel broken
- Item: chair wheel broken

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <e…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Good news - TKT-2026-0001 (Chair wheel broken) has been taken care of.

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Chair wheel broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair wheel broken

Completed by Facilities & Maintenance

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 4

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Furniture
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: BrightFurniture Co

Details:
- Location: cabin 4
- Issue: chair wheel broken
- Item: chair wheel broken


Regards,
Workplace Team
```

#### test_requester_confirmation_is_a_verified_closure — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "chair". They wrote: "chair wheel broken in cabin 4"
2. facilities@acme-real.com sent an email. Subject: "Re: Work Order: Chair wheel broken [TKT-2026-0001]". They wrote: "done"
3. arjun.singh@acme.demo sent an email. Subject: "Re: chair". They wrote: "thanks, all good now"
4. The desk opened TKT-2026-0001 (Chair wheel broken) — closed.
5. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 4 repairs. The records did not call for a replacement, so this stayed a normal repair.
6. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair wheel broken [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Chair wheel broken Repair This item. Repairs…"
7. It wrote to arjun.singh@acme.demo. Subject: "Re: chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
8. It wrote to arjun.singh@acme.demo. Subject: "chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Good news - TKT-2026-0001 (Chair wheel broken) has been taken care of. If anything is still not right, just reply "not fixed" and I'll reopen…"
9. It wrote to ops-desk@example.com. Subject: "Ops Update: Chair wheel broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair wheel broken Completed by Facilities & Maintenance Record check: - Item: no …"
10. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair wheel broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair wheel broken Thanks for completing this. To close it as verified, please rep…"
11. It wrote to arjun.singh@acme.demo. Subject: "Re: chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Request TKT-2026-0001 has been closed. Thank you for confirming. Regards, Workplace Team"
12. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Chair wheel broken (CLOSED, MEDIUM, stage CLOSED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: chair

```
chair wheel broken in cabin 4
```

- From: facilities@acme-real.com
- Subject: Re: Work Order: Chair wheel broken [TKT-2026-0001]

```
done
```

- From: arjun.singh@acme.demo
- Subject: Re: chair

```
thanks, all good now
```

Reply sent:

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair wheel broken [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Chair wheel broken

Repair This item. Repairs on record: 0 of 4.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 4

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Furniture
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: BrightFurniture Co

Investigation:
Approved vendor on file: BrightFurniture Co; Route to Facilities & Maintenance

Details:
- Location: cabin 4
- Issue: chair wheel broken
- Item: chair wheel broken

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <e…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Good news - TKT-2026-0001 (Chair wheel broken) has been taken care of.

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Chair wheel broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair wheel broken

Completed by Facilities & Maintenance

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 4

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Furniture
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: BrightFurniture Co

Details:
- Location: cabin 4
- Issue: chair wheel broken
- Item: chair wheel broken


Regards,
Workplace Team
```

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair wheel broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair wheel broken

Thanks for completing this. To close it as verified, please reply with what was fixed or done (a photo works too) (or attach a photo).

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 4

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Furniture
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: BrightFurniture Co

Details:
- Location: cabin 4
- Issue: chair wheel broken
- Item: chair wheel broken


Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Request TKT-2026-0001 has been closed. Thank you for confirming.

Regards,
Workplace Team
```

#### test_unverified_question_goes_to_a_person_instead_of_a_guess — FAILED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "leave". They wrote: "how many days of paternity leave do we get?"
2. The desk opened TKT-2026-0001 (Question: Paternity leave days) — handed to the team and still open.
3. It checked the records. Nothing in the records blocked it, so the desk carried on.
4. It wrote to ops-desk@example.com. Subject: "Work Order: Question: Paternity leave days [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Question: Paternity leave days Question need…"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: leave [TKT-2026-0001]". The message starts: "Dear Arjun Singh, A verified answer is not on record for that question. It has been referred to the administrator (TKT-2026-0001). The reply will come on this …"
6. Result: this test failed. The replies above were still written, and the failure is noted at the end of this case.


Case state:

- TKT-2026-0001: Question: Paternity leave days (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: arjun.singh@acme.demo
- Subject: leave

```
how many days of paternity leave do we get?
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Question: Paternity leave days [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Question: Paternity leave days

Question needs a verified answer - reply "tell requester: <answer>"
(No Admin & Workplace contact set yet - sent to you. Add it in Company setup.)

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: General admin request
Team: Admin & Workplace
Due by: 18 Oct, 11:47 PM

Details:
- Question: how many days of paternity leave do we get?

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
If the team, type, or priority is wrong, reply "change team to <tea…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: leave [TKT-2026-0001]

```
Dear Arjun Singh,

A verified answer is not on record for that question. It has been referred to the administrator (TKT-2026-0001). The reply will come on this thread.

Regards,
Workplace Team
```

Failure:

```
E   AssertionError: assert ('10 days' not in 'Dear Arjun ...place Team\n'
      
      '10 days' is contained here:
      ? ----
        place Team and 'rather than guess' in 'Dear Arjun Singh,\n\nA verified answer is not on record for that question. It has been referred to the administrator (TKT-2026-0001). The reply will come on this thread.\n\nRegards,\nWorkplace Team\n')
```

#### test_model_admitting_it_does_not_know_is_also_routed — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "what are the gym timings?"
2. The desk opened TKT-2026-0001 (Question: Gym timings) — handed to the team and still open.
3. It checked the records. Nothing in the records blocked it, so the desk carried on.
4. It wrote to ops-desk@example.com. Subject: "Work Order: Question: Gym timings [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Question: Gym timings Question needs a verif…"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [TKT-2026-0001]". The message starts: "Dear Arjun Singh, A verified answer is not on record for that question. It has been referred to the administrator (TKT-2026-0001). The reply will come on this …"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Question: Gym timings (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
what are the gym timings?
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Question: Gym timings [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Question: Gym timings

Question needs a verified answer - reply "tell requester: <answer>"
(No Admin & Workplace contact set yet - sent to you. Add it in Company setup.)

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: General admin request
Team: Admin & Workplace
Due by: 18 Oct, 11:47 PM

Details:
- Question: what are the gym timings?

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
If the team, type, or priority is wrong, reply "change team to <team>", "change type to <type>…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [TKT-2026-0001]

```
Dear Arjun Singh,

A verified answer is not on record for that question. It has been referred to the administrator (TKT-2026-0001). The reply will come on this thread.

Regards,
Workplace Team
```

#### test_flight_booking_needs_approval_but_a_cab_to_the_airport_does_not — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "please book a flight Delhi to Mumbai on Friday"
2. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "need a cab from office to airport friday 6 am, I have a flight"
3. The desk opened TRV-2026-0001 (Flight to Mumbai) — waiting for approval; TRV-2026-0002 (Cab to airport) — handed to the team and still open.
4. It checked the records. Nothing in the records blocked it, so the desk carried on.
5. It wrote to ops-desk@example.com. Subject: "Ops Decision: Flight to Mumbai [TRV-2026-0001]". The message starts: "Ops Decision: Flight to Mumbai [TRV-2026-0001]"
6. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [TRV-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged and sent for approval. Request: TRV-2026-0001 Subject: Flight to Mumbai You will be updated on this thread once …"
7. It wrote to ops-desk@example.com. Subject: "Work Order: Cab to airport [TRV-2026-0002]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TRV-2026-0002 Subject: Cab to airport New work order (No Travel Des…"
8. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [TRV-2026-0002]". The message starts: "Dear Arjun Singh, We have logged your request and assigned it to Travel Desk. Request: TRV-2026-0002 Subject: Cab to airport Status: Open You will be updated o…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TRV-2026-0001: Flight to Mumbai (ACTIVE, MEDIUM, stage AWAITING_APPROVAL, decision PROCEED)
- TRV-2026-0002: Cab to airport (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
please book a flight Delhi to Mumbai on Friday
```

- From: arjun.singh@acme.demo
- Subject: Request

```
need a cab from office to airport friday 6 am, I have a flight
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Flight to Mumbai [TRV-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: TRV-2026-0001
Subject: Flight to Mumbai

Needs your approval - flight / train / hotel bookings need approval before booking

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Travel / cab
Team: Travel Desk

Details:
- Travel date: Friday 9 Oct
- From: Delhi
- To: Mumbai
- Pickup: Delhi

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [TRV-2026-0001]

```
Dear Arjun Singh,

Your request has been logged and sent for approval.

Request: TRV-2026-0001
Subject: Flight to Mumbai

You will be updated on this thread once a decision is recorded.

Possible flight timings (schedule only — fares are confirmed by Travel Desk, not auto-quoted):

Travel Desk has the request and will send exact airline / time / fare options on this thread.
Reply with the option number (or preferred time window). I'll ask Travel Desk to lock it after approval if required.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Cab to airport [TRV-2026-0002]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TRV-2026-0002
Subject: Cab to airport

New work order
(No Travel Desk contact set yet - sent to you. Add it in Company setup.)

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Travel / cab
Team: Travel Desk
Due by: 18 Oct, 11:47 AM

Details:
- Travel date: Friday 6 AM
- Pickup: Office
- Destination: IGI T3
- Time: 6 AM

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <the booking reference / cab and driver details>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or priority i…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [TRV-2026-0002]

```
Dear Arjun Singh,

We have logged your request and assigned it to Travel Desk.

Request: TRV-2026-0002
Subject: Cab to airport
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

#### test_catering_without_a_cost_and_weekend_access_need_sign_off — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "lunch for 20 people on monday 1pm for the client team"
2. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "AC vendor needs weekend access to the 3rd floor for servicing"
3. The desk opened CAT-2026-0001 (Lunch for 20) — waiting for approval; TKT-2026-0001 (AC vendor weekend work) — waiting for approval.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. Nothing in the records blocked it, so the desk carried on.
5. It wrote to ops-desk@example.com. Subject: "Ops Decision: Lunch for 20 [CAT-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: CAT-2026-0001 Subject: Lunch for 20 Needs your approval - catering is chargeable - c…"
6. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [CAT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged and sent for approval. Request: CAT-2026-0001 Subject: Lunch for 20 You will be updated on this thread once a de…"
7. It wrote to ops-desk@example.com. Subject: "Ops Decision: AC vendor weekend work [TKT-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: TKT-2026-0001 Subject: AC vendor weekend work Needs your approval - after-hours / ho…"
8. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged and sent for approval. Request: TKT-2026-0001 Subject: AC vendor weekend work You will be updated on this thread…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- CAT-2026-0001: Lunch for 20 (ACTIVE, MEDIUM, stage AWAITING_APPROVAL, decision PROCEED)
- TKT-2026-0001: AC vendor weekend work (ACTIVE, MEDIUM, stage AWAITING_APPROVAL, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
lunch for 20 people on monday 1pm for the client team
```

- From: arjun.singh@acme.demo
- Subject: Request

```
AC vendor needs weekend access to the 3rd floor for servicing
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Lunch for 20 [CAT-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: CAT-2026-0001
Subject: Lunch for 20

Needs your approval - catering is chargeable - cost sign-off needed before ordering

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Catering
Team: Cafeteria & Catering
Preferred vendor: FreshServe Catering Pvt. Ltd. <orders@freshserve.demo>

Details:
- Date: Monday 1 PM
- Headcount: 20
- Time: 1 PM

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [CAT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged and sent for approval.

Request: CAT-2026-0001
Subject: Lunch for 20

You will be updated on this thread once a decision is recorded.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: AC vendor weekend work [TKT-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: TKT-2026-0001
Subject: AC vendor weekend work

Needs your approval - after-hours / holiday access needs admin sign-off

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Air conditioning
Team: Facilities & Maintenance

Details:
- Location: 3rd floor
- Issue: AC servicing

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged and sent for approval.

Request: TKT-2026-0001
Subject: AC vendor weekend work

You will be updated on this thread once a decision is recorded.

Regards,
Workplace Team
```

#### test_decision_classes — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_overdue_approval_puts_case_at_risk_until_decided — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "Need server room access"
2. The desk opened ITS-2026-0001 (Server room access) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 3 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to ops-desk@example.com. Subject: "Ops Decision: Server room access [ITS-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: ITS-2026-0001 Subject: Server room access Needs your approval - access card requests…"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [ITS-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged and sent for approval. Request: ITS-2026-0001 Subject: Server room access You will be updated on this thread onc…"
6. It wrote to ops-desk@example.com. Subject: "Ops Decision: Server room access [ITS-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: ITS-2026-0001 Subject: Server room access Reminder - still waiting for your approval…"
7. It wrote to ops-desk@example.com. Subject: "Ops Decision: Server room access [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Server room access Repair This item. Repairs…"
8. It wrote to arjun.singh@acme.demo. Subject: "Request [ITS-2026-0001]". The message starts: "Dear Arjun Singh, Request ITS-2026-0001 (Server room access) is approved and assigned to IT Support. You will be updated on this thread when the work is comple…"
9. It wrote to ops-desk@example.com. Subject: "Ops Decision: Server room access [ITS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ITS-2026-0001 Subject: Server room access Approved via dashboard by ops-desk@example.com Record check: - …"
10. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Server room access (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
Need server room access
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Server room access [ITS-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: ITS-2026-0001
Subject: Server room access

Needs your approval - access card requests need admin sign-off

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 3

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Access card / ID
Team: IT Support

Details:
- Area: server room

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [ITS-2026-0001]

```
Dear Arjun Singh,

Your request has been logged and sent for approval.

Request: ITS-2026-0001
Subject: Server room access

You will be updated on this thread once a decision is recorded.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Server room access [ITS-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: ITS-2026-0001
Subject: Server room access

Reminder - still waiting for your approval (access card requests need admin sign-off)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 3

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Access card / ID
Team: IT Support

Details:
- Area: server room

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Server room access [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Server room access

Repair This item. Repairs on record: 0 of 3.
(No IT Support contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 3

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Access card / ID
Team: IT Support
Due by: 18 Oct, 7:47 AM

Details:
- Area: server room

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <the card number issued or access granted>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The requ…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Request [ITS-2026-0001]

```
Dear Arjun Singh,

Request ITS-2026-0001 (Server room access) is approved and assigned to IT Support. You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Decision: Server room access [ITS-2026-0001]

```
Dear Team,

Please note the following update.

Request: ITS-2026-0001
Subject: Server room access

Approved via dashboard by ops-desk@example.com

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 3

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Access card / ID
Team: IT Support
Due by: 18 Oct, 7:47 AM

Details:
- Area: server room


Regards,
Workplace Team
```

#### test_emergency_stop_skips_ai_but_keeps_safety_path — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "fan". They wrote: "Fan not working in cabin 12"
2. arjun.singh@acme.demo sent an email. Subject: "sparks". They wrote: "socket sparking near desk 4, smoke coming"
3. The desk opened TKT-2026-0001 (Fan not working in cabin 12) — waiting for approval; EHS-2026-0001 (socket sparking near desk 4, smoke coming) — handed to the team and still open.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
5. It wrote to ops-desk@example.com. Subject: "Ops Decision: Fan not working in cabin 12 [TKT-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: TKT-2026-0001 Subject: Fan not working in cabin 12 Needs your approval - the AI assi…"
6. It wrote to arjun.singh@acme.demo. Subject: "Re: fan [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged and sent for approval. Request: TKT-2026-0001 Subject: Fan not working in cabin 12 You will be updated on this t…"
7. It wrote to ops-desk@example.com. Subject: "Urgent: socket sparking near desk 4, smoke coming [EHS-2026-0001]". The message starts: "Dear Team, The following request is urgent and requires attention. Request: EHS-2026-0001 Subject: socket sparking near desk 4, smoke coming URGENT - safety / …"
8. It wrote to ops-desk@example.com. Subject: "Urgent: socket sparking near desk 4, smoke coming [EHS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: EHS-2026-0001 Subject: socket sparking near desk 4, smoke coming UR…"
9. It wrote to arjun.singh@acme.demo. Subject: "Re: sparks [EHS-2026-0001]". The message starts: "Hi Arjun, Thanks for letting us know. I've logged this as EHS-2026-0001 and passed it to the right team - we'll keep you posted here. Workplace Team"
10. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Fan not working in cabin 12 (ACTIVE, MEDIUM, stage AWAITING_APPROVAL, decision REPAIR)
- EHS-2026-0001: socket sparking near desk 4, smoke coming (ACTIVE, URGENT, stage DISPATCHED, decision PROCEED)

Email received:

- From: arjun.singh@acme.demo
- Subject: fan

```
Fan not working in cabin 12
```

- From: arjun.singh@acme.demo
- Subject: sparks

```
socket sparking near desk 4, smoke coming
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Fan not working in cabin 12 [TKT-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: TKT-2026-0001
Subject: Fan not working in cabin 12

Needs your approval - the AI assistant is paused (emergency stop) - please confirm before the desk acts

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance

What they asked: Fan not working in cabin 12

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: fan [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged and sent for approval.

Request: TKT-2026-0001
Subject: Fan not working in cabin 12

You will be updated on this thread once a decision is recorded.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Urgent: socket sparking near desk 4, smoke coming [EHS-2026-0001]

```
Dear Team,

The following request is urgent and requires attention.

Request: EHS-2026-0001
Subject: socket sparking near desk 4, smoke coming

URGENT - safety / business-stopping signal: "sparking"

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Health & safety
Team: Facilities & Maintenance
Priority: Urgent (safety / business-stopping signal: "sparking")

What they asked: socket sparking near desk 4, smoke coming

Please reply "assign to <email>" to transfer it, "tell requester: <message>" to update the requester, "done - <note>" if it is already complete, or "cancel".

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Urgent: socket sparking near desk 4, smoke coming [EHS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: EHS-2026-0001
Subject: socket sparking near desk 4, smoke coming

URGENT work order - please act now
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Health & safety
Team: Facilities & Maintenance
Priority: Urgent (safety / business-stopping signal: "sparking")
Due by: 18 Oct, 3:47 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

What they asked: socket sparking near desk 4, smoke coming

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <em…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: sparks [EHS-2026-0001]

```
Hi Arjun,

Thanks for letting us know. I've logged this as EHS-2026-0001 and passed it to the right team - we'll keep you posted here.

Workplace Team
```

#### test_verified_cases_become_precedent_and_corrections_lower_automation — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "chair". They wrote: "chair wheel broken in cabin 4"
2. ops-desk@example.com sent an email. Subject: "Re: Work Order: Chair wheel broken [TKT-2026-0001]". They wrote: "change location to cabin 5"
3. facilities@acme-real.com sent an email. Subject: "Re: Work Order: Chair wheel broken [TKT-2026-0001]". They wrote: "done, replaced the wheel castor"
4. arjun.singh@acme.demo sent an email. Subject: "chair 2". They wrote: "chair wheel broken in cabin 9"
5. The desk opened TKT-2026-0001 (Chair wheel broken) — closed; TKT-2026-0002 (Another chair) — handed to the team and still open.
6. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 4 repairs. The records did not call for a replacement, so this stayed a normal repair.
7. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair wheel broken [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Chair wheel broken Repair This item. Repairs…"
8. It wrote to arjun.singh@acme.demo. Subject: "Re: chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
9. It wrote to arjun.singh@acme.demo. Subject: "chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, A quick update on TKT-2026-0001 (Chair wheel broken): location is now cabin 5. Reply here if that doesn't work for you. Regards, Workplace Te…"
10. It wrote to arjun.singh@acme.demo. Subject: "chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Good news - TKT-2026-0001 (Chair wheel broken) has been taken care of. Note from Facilities & Maintenance: replaced the wheel castor If anyth…"
11. It wrote to ops-desk@example.com. Subject: "Ops Update: Chair wheel broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair wheel broken Completed by Facilities & Maintenance: replaced the wheel casto…"
12. It wrote to facilities@acme-real.com. Subject: "Work Order: Another chair [TKT-2026-0002]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0002 Subject: Another chair Repair This item. Repairs on r…"
13. It wrote to arjun.singh@acme.demo. Subject: "Re: chair 2 [TKT-2026-0002]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
14. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Chair wheel broken (CLOSED, MEDIUM, stage CLOSED, decision REPAIR)
- TKT-2026-0002: Another chair (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: chair

```
chair wheel broken in cabin 4
```

- From: ops-desk@example.com
- Subject: Re: Work Order: Chair wheel broken [TKT-2026-0001]

```
change location to cabin 5
```

- From: facilities@acme-real.com
- Subject: Re: Work Order: Chair wheel broken [TKT-2026-0001]

```
done, replaced the wheel castor
```

- From: arjun.singh@acme.demo
- Subject: chair 2

```
chair wheel broken in cabin 9
```

Reply sent:

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair wheel broken [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Chair wheel broken

Repair This item. Repairs on record: 0 of 4.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 4

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Furniture
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: BrightFurniture Co

Investigation:
Approved vendor on file: BrightFurniture Co; Route to Facilities & Maintenance

Details:
- Location: cabin 4
- Issue: chair wheel broken
- Item: chair wheel broken

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <e…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: chair [TKT-2026-0001]

```
Dear Arjun Singh,

A quick update on TKT-2026-0001 (Chair wheel broken): location is now cabin 5.

Reply here if that doesn't work for you.

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Good news - TKT-2026-0001 (Chair wheel broken) has been taken care of.
Note from Facilities & Maintenance: replaced the wheel castor

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Chair wheel broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair wheel broken

Completed by Facilities & Maintenance: replaced the wheel castor

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 4

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Furniture
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: BrightFurniture Co

Details:
- Location: cabin 5
- Issue: chair wheel broken
- Item: chair wheel broken


Regards,
Workplace Team
```

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Another chair [TKT-2026-0002]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0002
Subject: Another chair

Repair This item. Repairs on record: 0 of 4.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 4

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Furniture
Team: Facilities & Maintenance
Due by: 18 Oct, 7:47 AM
Preferred vendor: BrightFurniture Co

Investigation:
Prior related work: Auto-closed after resolution (verified_evidence); Approved vendor on file: BrightFurniture Co; Route to Facilities & Maintenance

Details:
- Location: cabin 9
- Issue: chair wheel broken
- Item: chair wheel broken

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "don…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair 2 [TKT-2026-0002]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0002)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

#### test_dashboard_kpis_expose_automation — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_booking_lifecycle.py

19 cases, 0 failed.

#### test_room_taken_at_that_time_is_skipped_but_free_on_another_day — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 5 on 15th october at 3 pm–5pm (2.0h)) — still open; ROOM-2026-0002 (Meeting for 5 on 15th october at 3 pm–5pm (2.0h)) — still open; ROOM-2026-0003 (Meeting for 5 on 16th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 15th o…"
3. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release…"
4. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Huddle Room F2-R2 Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corpora…"
5. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0002]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Focus Room 5A (seats 8) Your booking: - Attendees: 5 - Date: 15th octob…"
6. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 16th october at 3 pm–5pm (2.0h) [ROOM-2026-0003]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 16th o…"
7. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)
- ROOM-2026-0002: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)
- ROOM-2026-0003: Meeting for 5 on 16th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 5

To arrange:
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0002]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Focus Room 5A (seats 8)

Your booking:
- Attendees: 5
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0002
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 16th october at 3 pm–5pm (2.0h) [ROOM-2026-0003]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 16th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0003
```

#### test_room_status_is_never_flipped_globally — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 5 on 15th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 15th o…"
3. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release…"
4. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Huddle Room F2-R2 Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corpora…"
5. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 5

To arrange:
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

#### test_hold_reminder_then_expiry_then_confirm_rebooks — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 5 on 15th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 15th o…"
3. It wrote to employee1@acme.demo. Subject: "Reminder: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Huddle Room F2-R2 is still held for you until 18 Oct, 11:47 PM IST. Reply "confirm" to lock it in, or tell us what to change. Case: ROOM-2026-…"
4. It wrote to employee1@acme.demo. Subject: "Hold Released: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, We held Huddle Room F2-R2 for you but didn't hear back, so the hold has been released. Reply "confirm" and we'll book it if it's still free (o…"
5. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release…"
6. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Huddle Room F2-R2 Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corpora…"
7. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Reminder: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Huddle Room F2-R2 is still held for you until 18 Oct, 11:47 PM IST.

Reply "confirm" to lock it in, or tell us what to change.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Hold Released: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

We held Huddle Room F2-R2 for you but didn't hear back, so the hold has been released.

Reply "confirm" and we'll book it if it's still free (or offer the next best room), or tell us what to change.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 5

To arrange:
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

#### test_requester_cancel_releases_room — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 5 on 15th october at 3 pm–5pm (2.0h)) — cancelled.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 15th o…"
3. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release…"
4. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Huddle Room F2-R2 Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corpora…"
5. It wrote to employee1@acme.demo. Subject: "Cancelled: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting-room request has been cancelled. Huddle Room F2-R2 has been released. If you need a room again, just send a new request. Case: RO…"
6. It wrote to ops-desk@example.com. Subject: "Ops Update: Case cancelled by requester [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Case cancelled by requester Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office …"
7. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) (CANCELLED, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 5

To arrange:
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Cancelled: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting-room request has been cancelled.

Huddle Room F2-R2 has been released.

If you need a room again, just send a new request.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Case cancelled by requester [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Case cancelled by requester

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 5

To arrange:
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

Released: Huddle Room F2-R2. Reason: cancel

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

#### test_admin_cancel_via_gemini — PASSED

What happened:

1. Ops Desk <ops-desk@example.com> sent an email. Subject: "Re: [OPS UPDATE] [ROOM-2026-0001] briefing". They wrote: "kill this one, event postponed"
2. The desk opened ROOM-2026-0001 (Meeting for 5 on 15th october at 3 pm–5pm (2.0h)) — cancelled.
3. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 15th o…"
4. It wrote to employee1@acme.demo. Subject: "Cancelled: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting-room request has been cancelled by our ops team. Reason: Event postponed Huddle Room F2-R2 has been released. If you need a room …"
5. It wrote to ops-desk@example.com. Subject: "Ops Update: Case cancelled by ops [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Case cancelled by ops Released: Huddle Room F2-R2. Reason: Event postponed Requester: employee1@acme.demo When…"
6. It wrote to ops-desk@example.com. Subject: "Ops Done: CANCEL: Case cancelled, room released, requester told. [ROOM-2026-0001]". The message starts: "Done — Case cancelled, room released, requester told. Case: ROOM-2026-0001"
7. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) (CANCELLED, MEDIUM)

Email received:

- From: Ops Desk <ops-desk@example.com>
- Subject: Re: [OPS UPDATE] [ROOM-2026-0001] briefing

```
kill this one, event postponed
```

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Cancelled: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting-room request has been cancelled by our ops team.

Reason: Event postponed

Huddle Room F2-R2 has been released.

If you need a room again, just send a new request.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Case cancelled by ops [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Case cancelled by ops
Released: Huddle Room F2-R2. Reason: Event postponed

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
People: 5
Also asked: orchestrator role: module_helper

No action needed. To change anything, please reply, for example "move them to F2-R3", "make it 20 people", or "cancel".
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Done: CANCEL: Case cancelled, room released, requester told. [ROOM-2026-0001]

```
Done — Case cancelled, room released, requester told.

Case: ROOM-2026-0001
```

#### test_headcount_change_after_booking_moves_room — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 14 on 15th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 15th o…"
3. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release…"
4. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Huddle Room F2-R2 Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corpora…"
5. It wrote to employee1@acme.demo. Subject: "Room Changed: Meeting for 14 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Huddle Room F2-R2 no longer fits after your change, so we moved you to Conference Room 8B (seats 16). - attendees: 14 Case: ROOM-2026-0001"
6. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking moved — Huddle Room F2-R2 → Conference Room 8B [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking moved — Huddle Room F2-R2 → Conference Room 8B Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3…"
7. It wrote to ops-desk@example.com. Subject: "Ops Update: Task list updated after a change [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Task list updated after a change Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Of…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 14 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 5

To arrange:
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Room Changed: Meeting for 14 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Huddle Room F2-R2 no longer fits after your change, so we moved you to Conference Room 8B (seats 16).

- attendees: 14

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking moved — Huddle Room F2-R2 → Conference Room 8B [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking moved — Huddle Room F2-R2 → Conference Room 8B

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Conference Room 8B (16 seats), setup 30 min before
People: 14

To arrange:
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Task list updated after a change [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Task list updated after a change

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Conference Room 8B (16 seats), setup 30 min before
People: 14

To arrange:
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Conference Room 8B after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

Administration:
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM
- Final room inspection before setup time
- Clean and reset Conference Room 8B after the meeting

No action is required. To change the booking, please repl…
```

#### test_time_change_after_booking_keeps_room_when_free — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 5 on 15th october at 11 am–1 pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 15th o…"
3. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release…"
4. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Huddle Room F2-R2 Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corpora…"
5. It wrote to employee1@acme.demo. Subject: "Booking Updated: Meeting for 5 on 15th october at 11 am–1 pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Done — Huddle Room F2-R2 still works for the change, so your booking is updated. - preferred time: 11 am - end time: 1 pm Case: ROOM-2026-0001"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 5 on 15th october at 11 am–1 pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 5

To arrange:
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Booking Updated: Meeting for 5 on 15th october at 11 am–1 pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Done — Huddle Room F2-R2 still works for the change, so your booking is updated.

- preferred time: 11 am
- end time: 1 pm

Case: ROOM-2026-0001
```

#### test_larger_venue_choice_holds_offsite_venue — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 80 on 15th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "No Room Available: Meeting for 80 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, No room fits 80 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40…"
3. It wrote to ops-desk@example.com. Subject: "Ops Decision: No suitable room in inventory [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: No suitable room in inventory No room fits 80 people in person (largest inventory room holds 40). Requester: e…"
4. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 80 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, You chose a larger venue — Hyatt Ballroom (seats 120) is free at that time. Venue (off-site): Hyatt Ballroom (seats 120) Your booking: - Atten…"
5. It wrote to ops-desk@example.com. Subject: "Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Requester selected alternative — Escalate for a larger venue / off-site option — Hyatt Ballroom (seats 120) is…"
6. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 80 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Hyatt Ballroom Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release) N…"
7. It wrote to ops-desk@example.com. Subject: "Ops Decision: Booking confirmed — Hyatt Ballroom [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Hyatt Ballroom Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corporate …"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 80 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 80 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

No room fits 80 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option — Hyatt Ballroom (seats 120) is free
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: No suitable room in inventory [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: No suitable room in inventory
No room fits 80 people in person (largest inventory room holds 40).

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
People: 80
Also asked: orchestrator role: module_helper
Room: none fits — No room fits 80 people in person (largest inventory room holds 40).

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 80 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

You chose a larger venue — Hyatt Ballroom (seats 120) is free at that time.

Venue (off-site): Hyatt Ballroom (seats 120)

Your booking:
- Attendees: 80
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: internal meeting
- Hybrid / AV: no
- Presentation display: no
- Location preference: Corporate Office
- Catering / amenities: none
- Confidentiality: standard
- Also requested: orchestrator role: module_helper
- Also requested: spine template: MEETING_ROOM

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Requester selected alternative — Escalate for a larger venue / off-site opti [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Requester selected alternative — Escalate for a larger venue / off-site option — Hyatt Ballroom (seats 120) is free
Follow through on this alternative (book off-site, split, reschedule, etc.).

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
People: 80
Also asked: orchestrator role: module_helper; spine template: MEETING_ROOM
Room: Hyatt Ballroom (120 seats) — held, waiting for the requester to confirm

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 80 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Hyatt Ballroom
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

No visitor, parking, catering or billing modules were activated.
Cost approval will cover only external / off-site venue.
The chargeable items are waiting for cost approval — everything else goes ahead now, and I'll confirm once it's approved.
Assumptions:
- Video conferencing treated as not required under internal-meeting rule MP-INT-006; reply to correct before the change cutoff.


When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Booking confirmed — Hyatt Ballroom [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Hyatt Ballroom

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Hyatt Ballroom (120 seats), setup 30 min before
People: 80

To arrange:
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Hyatt Ballroom after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

Cost approval needed — it covers only the chargeable part:
Cost centre: EN-2101 (Engineering)
Chargeable:
- External / off-site venue: 1 = to be quoted
Estimated chargeable total: Rs 0 before tax + items to be quoted

Reply "approve" or "reje…
```

#### test_split_choice_books_several_rooms — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 50 on 15th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "No Room Available: Meeting for 50 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, No room fits 50 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40…"
3. It wrote to ops-desk@example.com. Subject: "Ops Decision: No suitable room in inventory [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: No suitable room in inventory No room fits 50 people in person (largest inventory room holds 40). Requester: e…"
4. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 50 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, You chose to split the group — these rooms are free at the same time. Rooms (your group split across them): Auditorium A (seats 40), Learning …"
5. It wrote to ops-desk@example.com. Subject: "Ops Decision: Requester selected alternative — Split into two rooms (~25 + 25) — Auditoriu [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Requester selected alternative — Split into two rooms (~25 + 25) — Auditorium A + Learning Studio A are free F…"
6. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 50 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Auditorium A + Learning Studio A Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5p…"
7. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Auditorium A + Learning Studio A [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Auditorium A + Learning Studio A Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 p…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 50 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 50 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

No room fits 50 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option
- Split into two rooms (~25 + 25) — Auditorium A + Learning Studio A are free

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: No suitable room in inventory [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: No suitable room in inventory
No room fits 50 people in person (largest inventory room holds 40).

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
People: 50
Also asked: orchestrator role: module_helper
Room: none fits — No room fits 50 people in person (largest inventory room holds 40).

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 50 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

You chose to split the group — these rooms are free at the same time.

Rooms (your group split across them): Auditorium A (seats 40), Learning Studio A (seats 30)

Your booking:
- Attendees: 50
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: internal meeting
- Hybrid / AV: no
- Presentation display: no
- Location preference: Corporate Office
- Catering / amenities: none
- Confidentiality: standard
- Also requested: orchestrator role: module_helper
- Also requested: spine template: MEETING_ROOM

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Requester selected alternative — Split into two rooms (~25 + 25) — Auditoriu [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Requester selected alternative — Split into two rooms (~25 + 25) — Auditorium A + Learning Studio A are free
Follow through on this alternative (book off-site, split, reschedule, etc.).

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
People: 50
Also asked: orchestrator role: module_helper; spine template: MEETING_ROOM
Room: Auditorium A + Learning Studio A (70 seats) — held, waiting for the requester to confirm

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 50 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Auditorium A + Learning Studio A
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
Assumptions:
- Video conferencing treated as not required under internal-meeting rule MP-INT-006; reply to correct before the change cutoff.

After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Auditorium A + Learning Studio A [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Auditorium A + Learning Studio A

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Auditorium A + Learning Studio A (70 seats), setup 30 min before
People: 50

To arrange:
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Auditorium A + Learning Studio A after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

#### test_gemini_none_choice_overrides_regex — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 80 on 15th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "No Room Available: Meeting for 80 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, No room fits 80 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40…"
3. It wrote to ops-desk@example.com. Subject: "Ops Decision: No suitable room in inventory [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: No suitable room in inventory No room fits 80 people in person (largest inventory room holds 40). Requester: e…"
4. It wrote to employee1@acme.demo. Subject: "Update Noted: Meeting for 80 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Thanks — we've noted your additional request(s) against this case. - spine template: MEETING_ROOM We're still working the room options with op…"
5. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 80 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 80 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

No room fits 80 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: No suitable room in inventory [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: No suitable room in inventory
No room fits 80 people in person (largest inventory room holds 40).

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
People: 80
Also asked: orchestrator role: module_helper
Room: none fits — No room fits 80 people in person (largest inventory room holds 40).

Your call. Please reply with the decision, for example "approve", "reject, no budget", "book F2-R3", "split it", or "move to 3pm".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Update Noted: Meeting for 80 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Thanks — we've noted your additional request(s) against this case.
- spine template: MEETING_ROOM

We're still working the room options with ops.

Case: ROOM-2026-0001
```

#### test_every_extra_ask_is_kept — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_catering_approval_goes_to_manager_with_contract_rate — PASSED

What happened:

1. Manager <mgr@example.com> sent an email. Subject: "Re: [OPS UPDATE] [ROOM-2026-0001] briefing". They wrote: "approved"
2. The desk opened ROOM-2026-0001 (Meeting for 6 on 15th october at 3 pm–5pm (2.0h)) — still open.
3. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 6 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 6 - Date: 15th o…"
4. It wrote to mgr@example.com. Subject: "Approval Required: Approval needed — catering spend [ROOM-2026-0001]". The message starts: "ROOM-2026-0001 — Meeting for 6 on 15th october at 3 pm–5pm (2.0h) Approval needed (catering spend) — only for the chargeable part of this request. Requester: e…"
5. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 6 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release…"
6. It wrote to ops-desk@example.com. Subject: "Ops Decision: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Huddle Room F2-R2 Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corpora…"
7. It wrote to ops-desk@example.com. Subject: "Ops Update: Task list updated after cost approval [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Task list updated after cost approval Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corpora…"
8. It wrote to employee1@acme.demo. Subject: "Ops Approved: Meeting for 6 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your cost for working lunch (sponsored cafeteria meal) request has been approved by ops. Case: ROOM-2026-0001"
9. It wrote to mgr@example.com. Subject: "Ops Done: APPROVE: Approved: cost for working lunch (sponsored cafeteria meal). Requester informed. [ROOM-2026-0001]". The message starts: "Done — Approved: cost for working lunch (sponsored cafeteria meal). Requester informed. Case: ROOM-2026-0001"
10. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 6 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Email received:

- From: Manager <mgr@example.com>
- Subject: Re: [OPS UPDATE] [ROOM-2026-0001] briefing

```
approved
```

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 6 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 6
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: lunch
- Dietary: all veg
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: mgr@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Approval Required: Approval needed — catering spend [ROOM-2026-0001]

```
ROOM-2026-0001 — Meeting for 6 on 15th october at 3 pm–5pm (2.0h)

Approval needed (catering spend) — only for the chargeable part of this request.

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats) — booked
People: 6

Cost centre: EN-2101 (Engineering)
Chargeable:
- Working lunch (sponsored cafeteria meal): 6 people x Rs 600 = Rs 3,600 (contract rate)
Estimated chargeable total: Rs 3,600 before tax
Included at no incremental charge: meeting room, drinking water and standard bottles.

Reply "approve" or "reject, <reason>". Included site services go ahead without this approval.
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 6 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

Active preparations: catering.
No separate approval is needed for meeting room, drinking water and standard bottles. Cost approval will cover only working lunch (sponsored cafeteria meal).
The chargeable items are waiting for cost approval — everything else goes ahead now, and I'll confirm once it's approved.

When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 6

To arrange:
- Lunch — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
- Cafeteria: with you (no Cafeteria & Catering mailbox set yet)
    · Working lunch (sponsored cafeteria meal): 6 people — on hold until cost approval (we'll confirm)
    · Dietary: all veg
When the items with you are ready, reply "done" (or "issue: <what's blocking>…
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Task list updated after cost approval [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Task list updated after cost approval

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 6

To arrange:
- Lunch — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
- Cafeteria: with you (no Cafeteria & Catering mailbox set yet)
    · Working lunch (sponsored cafeteria meal): 6 people — cost approved
    · Dietary: all veg
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

Cafeteria:
- Working lunc…
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Approved: Meeting for 6 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your cost for working lunch (sponsored cafeteria meal) request has been approved by ops.

Case: ROOM-2026-0001
```

- To: mgr@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Done: APPROVE: Approved: cost for working lunch (sponsored cafeteria meal). Requester informed. [ROOM-2026-0001]

```
Done — Approved: cost for working lunch (sponsored cafeteria meal). Requester informed.

Case: ROOM-2026-0001
```

#### test_catering_under_limit_is_auto_approved — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 6 on 15th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 6 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 6 - Date: 15th o…"
3. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 6 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release…"
4. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Huddle Room F2-R2 Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corpora…"
5. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 6 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 6 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 6
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: lunch
- Dietary: all veg
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 6 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

Active preparations: catering.
No separate approval is needed for meeting room, drinking water and standard bottles. Cost approval will cover only working lunch (sponsored cafeteria meal).

When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 6

To arrange:
- Lunch — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
- Cafeteria: with you (no Cafeteria & Catering mailbox set yet)
    · Working lunch (sponsored cafeteria meal): 6 people — cost approved
    · Dietary: all veg
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To…
```

#### test_spoofed_ops_mail_is_not_applied — PASSED

What happened:

1. Ops Desk <ops-desk@example.com> sent an email. Subject: "Re: [OPS UPDATE] [ROOM-2026-0001] briefing". They wrote: "book Auditorium A"
2. The desk opened ROOM-2026-0001 (Meeting for 5 on 15th october at 3 pm–5pm (2.0h)) — still open.
3. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 15th o…"
4. It wrote to ops-desk@example.com. Subject: "Ops Not Applied: Unverified ops reply [ROOM-2026-0001]". The message starts: "A reply claiming to be from ops-desk@example.com on this case could not be verified (no SPF/DKIM pass for that domain and it wasn't a reply to our mail), so no…"
5. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Email received:

- From: Ops Desk <ops-desk@example.com>
- Subject: Re: [OPS UPDATE] [ROOM-2026-0001] briefing

```
book Auditorium A
```

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Not Applied: Unverified ops reply [ROOM-2026-0001]

```
A reply claiming to be from ops-desk@example.com on this case could not be verified (no SPF/DKIM pass for that domain and it wasn't a reply to our mail), so nothing was changed.

If it was you, reply directly to the case briefing mail instead.

Subject: Re: [OPS UPDATE] [ROOM-2026-0001] briefing
Case: ROOM-2026-0001
```

#### test_reply_to_our_briefing_is_trusted — PASSED

What happened:

1. Ops Desk <ops-desk@example.com> sent an email. Subject: "Re: [OPS UPDATE] [ROOM-2026-0001] briefing". They wrote: "book Auditorium A"
2. The desk opened ROOM-2026-0001 (Meeting for 5 on 15th october at 3 pm–5pm (2.0h)) — still open.
3. It wrote to ops-desk@example.com. Subject: "Ops Update: New meeting-room request opened [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: New meeting-room request opened Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Off…"
4. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 15th o…"
5. It wrote to ops-desk@example.com. Subject: "Ops Update: Room offered to requester — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Room offered to requester — Huddle Room F2-R2 Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm ·…"
6. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Auditorium A Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release) No …"
7. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Auditorium A [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Auditorium A Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Of…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Email received:

- From: Ops Desk <ops-desk@example.com>
- Subject: Re: [OPS UPDATE] [ROOM-2026-0001] briefing

```
book Auditorium A
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: New meeting-room request opened [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: New meeting-room request opened

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
People: 5
Also asked: orchestrator role: module_helper

No action needed. To change anything, please reply, for example "move them to F2-R3", "make it 20 people", or "cancel".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Room offered to requester — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Room offered to requester — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
People: 5
Also asked: orchestrator role: module_helper
Room: Huddle Room F2-R2 (6 seats) — held, waiting for the requester to confirm

No action needed. To change anything, please reply, for example "move them to F2-R3", "make it 20 people", or "cancel".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Auditorium A
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Auditorium A [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Auditorium A

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Auditorium A (40 seats), setup 30 min before
People: 5

To arrange:
- Orchestrator role: module_helper

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Final room inspection before setup time
    · Clean and reset Auditorium A after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

#### test_reply_to_cloudmailin_bare_message_id_is_trusted — PASSED

What happened:

1. Ops Desk <ops-desk@example.com> sent an email. Subject: "Re: [OPS UPDATE] [ROOM-2026-0001] briefing". They wrote: "book Auditorium A"
2. The desk opened ROOM-2026-0001 (Meeting for 5 on 15th october at 3 pm–5pm (2.0h)) — still open.
3. It wrote to ops-desk@example.com. Subject: "Ops Update: New meeting-room request opened [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: New meeting-room request opened Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Off…"
4. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 15th o…"
5. It wrote to ops-desk@example.com. Subject: "Ops Update: Room offered to requester — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Room offered to requester — Huddle Room F2-R2 Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm ·…"
6. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Auditorium A Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release) No …"
7. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Auditorium A [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Auditorium A Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Of…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Email received:

- From: Ops Desk <ops-desk@example.com>
- Subject: Re: [OPS UPDATE] [ROOM-2026-0001] briefing

```
book Auditorium A
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: New meeting-room request opened [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: New meeting-room request opened

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
People: 5
Also asked: orchestrator role: module_helper

No action needed. To change anything, please reply, for example "move them to F2-R3", "make it 20 people", or "cancel".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Room offered to requester — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Room offered to requester — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
People: 5
Also asked: orchestrator role: module_helper
Room: Huddle Room F2-R2 (6 seats) — held, waiting for the requester to confirm

No action needed. To change anything, please reply, for example "move them to F2-R3", "make it 20 people", or "cancel".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Auditorium A
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Auditorium A [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Auditorium A

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Auditorium A (40 seats), setup 30 min before
People: 5

To arrange:
- Orchestrator role: module_helper

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Final room inspection before setup time
    · Clean and reset Auditorium A after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

#### test_gmail_plus_tag_recipient_accepts_base_from_reply — PASSED

What happened:

1. Facilities <flexxftw12@gmail.com> sent an email. Subject: "Re: [OPS UPDATE] [ROOM-2026-0001] briefing". They wrote: "book Auditorium A"
2. The desk opened ROOM-2026-0001 (Meeting for 5 on 15th october at 3 pm–5pm (2.0h)) — still open.
3. It wrote to ops-desk@example.com. Subject: "Ops Update: New meeting-room request opened [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: New meeting-room request opened Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Off…"
4. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 15th o…"
5. It wrote to flexxftw12+facilities@gmail.com. Subject: "Ops Update: Room offered to requester — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Room offered to requester — Huddle Room F2-R2 Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm ·…"
6. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Auditorium A Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release) No …"
7. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Auditorium A [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Auditorium A Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Of…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Email received:

- From: Facilities <flexxftw12@gmail.com>
- Subject: Re: [OPS UPDATE] [ROOM-2026-0001] briefing

```
book Auditorium A
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: New meeting-room request opened [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: New meeting-room request opened

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
People: 5
Also asked: orchestrator role: module_helper

No action needed. To change anything, please reply, for example "move them to F2-R3", "make it 20 people", or "cancel".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: flexxftw12+facilities@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Room offered to requester — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Room offered to requester — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
People: 5
Also asked: orchestrator role: module_helper
Room: Huddle Room F2-R2 (6 seats) — held, waiting for the requester to confirm

No action needed. To change anything, please reply, for example "move them to F2-R3", "make it 20 people", or "cancel".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Auditorium A
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Auditorium A [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Auditorium A

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Auditorium A (40 seats), setup 30 min before
People: 5

To arrange:
- Orchestrator role: module_helper

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Final room inspection before setup time
    · Clean and reset Auditorium A after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

#### test_spf_pass_for_sender_domain_is_trusted — PASSED

What happened:

1. Ops Desk <ops-desk@example.com> sent an email. Subject: "Re: [OPS UPDATE] [ROOM-2026-0001] briefing". They wrote: "book Auditorium A"
2. The desk opened ROOM-2026-0001 (Meeting for 5 on 15th october at 3 pm–5pm (2.0h)) — still open.
3. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 15th o…"
4. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Auditorium A Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release) No …"
5. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Auditorium A [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Auditorium A Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Of…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Email received:

- From: Ops Desk <ops-desk@example.com>
- Subject: Re: [OPS UPDATE] [ROOM-2026-0001] briefing

```
book Auditorium A
```

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 5 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Auditorium A
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Auditorium A [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Auditorium A

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Auditorium A (40 seats), setup 30 min before
People: 5

To arrange:
- Orchestrator role: module_helper

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Final room inspection before setup time
    · Clean and reset Auditorium A after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

#### test_booking_a_room_busy_for_another_case_is_refused — PASSED

What happened:

1. Ops Desk <ops-desk@example.com> sent an email. Subject: "Re: [OPS UPDATE] [ROOM-2026-0002] briefing". They wrote: "book Auditorium A"
2. The desk opened ROOM-2026-0001 (Meeting for 30 on 15th october at 3 pm–5pm (2.0h)) — still open; ROOM-2026-0002 (Meeting for 4 on 15th october at 3 pm–5pm (2.0h)) — still open.
3. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 30 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Auditorium A (seats 40) It's bigger than you need, but it's the best fr…"
4. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 30 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Auditorium A Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release) No …"
5. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Auditorium A [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Auditorium A Requester: employee1@acme.demo When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Of…"
6. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 4 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0002]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 4 - Date: 15th o…"
7. It wrote to ops-desk@example.com. Subject: "Ops Not Applied: BOOK: Auditorium A is already booked at that time for another case — nothing changed. Name [ROOM-2026-0002]". The message starts: "Not done — Auditorium A is already booked at that time for another case — nothing changed. Name a different room or venue. I read your reply as: Book Auditoriu…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 30 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)
- ROOM-2026-0002: Meeting for 4 on 15th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Email received:

- From: Ops Desk <ops-desk@example.com>
- Subject: Re: [OPS UPDATE] [ROOM-2026-0002] briefing

```
book Auditorium A
```

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 30 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Auditorium A (seats 40)
It's bigger than you need, but it's the best free fit for that time.

Your booking:
- Attendees: 30
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: internal meeting
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

Please double-check:
- Hybrid / AV: no

I've set these for you — reply if any should change:
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 30 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Auditorium A
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
Assumptions:
- Video conferencing treated as not required under internal-meeting rule MP-INT-006; reply to correct before the change cutoff.

After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Auditorium A [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Auditorium A

Requester: employee1@acme.demo
When: Thu 15 Oct 2026, 3 pm–5pm · Corporate Office
Room: Auditorium A (40 seats), setup 30 min before
People: 30

To arrange:
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Auditorium A after the meeting
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 4 on 15th october at 3 pm–5pm (2.0h) [ROOM-2026-0002]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 4
- Date: 15th october
- Time: 3 pm – 5pm
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0002
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Not Applied: BOOK: Auditorium A is already booked at that time for another case — nothing changed. Name [ROOM-2026-0002]

```
Not done — Auditorium A is already booked at that time for another case — nothing changed. Name a different room or venue.
I read your reply as: Book Auditorium A
Reply again in plain words, e.g. "approve", "book F2-R3" or "make it 20 people".

Case: ROOM-2026-0002
```

### test_branches.py

11 cases, 0 failed.

#### test_tree_lookup_and_labels — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_place_comes_from_details_then_home_branch_then_mail_text — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_nearest_team_wins_and_empty_branches_fall_back_up_the_tree — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_branch_admin_covers_its_branch_only — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_reroute_by_name_picks_the_branch_team — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_ai_catalogue_does_not_grow_with_branches — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_mail_from_pune_employee_reaches_the_pune_team — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "AC not cooling". They wrote: "The AC on our floor is not cooling."
2. The desk opened TKT-2026-0001 (AC not cooling) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to facilities.pune@acme.demo. Subject: "Work Order: AC not cooling [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: AC not cooling Repair This item. Repairs on …"
5. It wrote to rohan.mehta@acme.demo. Subject: "Re: AC not cooling [TKT-2026-0001]". The message starts: "Dear Rohan Mehta, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: AC not cooling (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: rohan.mehta@acme.demo
- Subject: AC not cooling

```
The AC on our floor is not cooling.
```

Reply sent:

- To: facilities.pune@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: AC not cooling [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: AC not cooling

Repair This item. Repairs on record: 0 of 6.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Air conditioning
Location: Pune > Pune Hinjewadi
Team: Facilities - Pune
Due by: 18 Oct, 11:47 PM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities - Pune

Details:
- Location: 4th floor

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <email>" to transfer the work…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: AC not cooling [TKT-2026-0001]

```
Dear Rohan Mehta,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities - Pune.

Regards,
Workplace Team
```

#### test_visiting_employee_is_served_by_the_branch_they_name — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "AC". They wrote: "I'm at Whitefield this week - the meeting room AC is dead."
2. The desk opened TKT-2026-0001 (AC not working) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to fac.blr@acme.demo. Subject: "Work Order: AC not working [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: AC not working Repair This item. Repairs on …"
5. It wrote to rohan.mehta@acme.demo. Subject: "Re: AC [TKT-2026-0001]". The message starts: "Dear Rohan, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001) As…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: AC not working (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: rohan.mehta@acme.demo
- Subject: AC

```
I'm at Whitefield this week - the meeting room AC is dead.
```

Reply sent:

- To: fac.blr@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: AC not working [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: AC not working

Repair This item. Repairs on record: 0 of 6.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Rohan <rohan.mehta@acme.demo>
Type: Air conditioning
Location: Bengaluru > Bengaluru Whitefield
Team: Facilities - Bengaluru
Due by: 18 Oct, 11:47 PM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities - Bengaluru

Details:
- Location: Whitefield

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <email>" to t…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: AC [TKT-2026-0001]

```
Dear Rohan,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities - Bengaluru.

Regards,
Workplace Team
```

#### test_import_people_and_teams_onto_branches — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_locations_preview_saves_nothing — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_setup_api_manages_places_and_team_scope — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_client_meeting.py

7 cases, 0 failed.

#### test_new_request_detection_same_thread — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_conditional_gaps_for_visitors_and_dietary — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_minimal_request_date_only_does_not_book — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 7 on 18 September 2026 at 11:00 AM–12:00 PM (1.0h)) — still open.
2. It wrote to arun.kumar@company.com. Subject: "Booking Confirmed: Meeting for 7 on 18 September 2026 at 11:00 AM–12:00 PM (1.0h) [ROOM-2026-0001]". The message starts: "Dear Arun Kumar, Your meeting room has been booked. Room: Focus Room 5A Date: 18 September 2026 Time: 11:00 AM – 12:00 PM Hold window: 11:00 AM (setup 30m earl…"
3. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 7 on 18 September 2026 at 11:00 AM–12:00 PM (1.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: arun.kumar@company.com
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 7 on 18 September 2026 at 11:00 AM–12:00 PM (1.0h) [ROOM-2026-0001]

```
Dear Arun Kumar,

Your meeting room has been booked.

Room: Focus Room 5A
Date: 18 September 2026
Time: 11:00 AM – 12:00 PM
Hold window: 11:00 AM (setup 30m earlier) – 12:00 PM (+15m release)
Case: ROOM-2026-0001

Active preparations: AV/display.
No separate approval is needed for meeting room, installed AV / VC and internal IT support.
Assumptions:
- Video conferencing treated as not required under internal-meeting rule MP-INT-006; reply to correct before the change cutoff.

If any detail is incorrect, reply to this email before the change cutoff.
After the meeting, reply "SATISFIED", "ISSUE REMAINS", or "REOPEN REQUEST".
```

#### test_client_meeting_propose_confirm_and_parallel_tracks — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 16 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h)) — still open.
2. It wrote to sales.employee@acme.demo. Subject: "Confirm Booking: Meeting for 16 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Sales Employee, Good news — I found a room that fits and I'm holding it for you. Room: Auditorium A (seats 40) It's bigger than you need, but it's the bes…"
3. It wrote to sales.employee@acme.demo. Subject: "Booking Confirmed: Meeting for 16 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Sales Employee, Your meeting room booking is confirmed. Room: Auditorium A Case: ROOM-2026-0001 Hold window: 2:00 PM (setup 45m earlier) – 5:00 PM (+30m r…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 16 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: sales.employee@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 16 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Sales Employee,

Good news — I found a room that fits and I'm holding it for you.

Room: Auditorium A (seats 40)
It's bigger than you need, but it's the best free fit for that time.

Your booking:
- Attendees: 16 + 6 visitors (6 visitors from ABC Industries) — 22 seats
- Date: 22 September 2026
- Time: 2:00 PM – 5:00 PM
- Meeting type: client review
- Hybrid / AV: yes — video/AV needed
- Presentation display: yes
- Location preference: Corporate Office
- Catering / amenities: high tea
- Dietary: 12 vegetarian, 4 non-vegetarian
- Special access / security: required
- Confidentiality: business confidential
- Guest vehicles: 3
- Vehicle number(s): DL01AB1234, HR26CD5678, UP16EF9012
- Also requested: orchestrator role: module_helper

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a diff…
```

- To: sales.employee@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 16 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Sales Employee,

Your meeting room booking is confirmed.

Room: Auditorium A
Case: ROOM-2026-0001
Hold window: 2:00 PM (setup 45m earlier) – 5:00 PM (+30m release)

Active preparations: catering, visitors, parking, AV/display.
No separate approval is needed for meeting room, tea / coffee (vending and pantry), drinking water and standard bottles, installed AV / VC and internal IT support, visitor access and reception, internal visitor parking. Cost approval will cover only high tea / snacks (special menu).
The chargeable items are waiting for cost approval — everything else goes ahead now, and I'll confirm once it's approved.

When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
- Whether recording is required.
After the meeting, just reply "satisfied" and we'll close it off.
```

#### test_new_meeting_on_same_thread_creates_second_outcome — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 4 on 22 September at 10 am (2.0h)) — still open; ROOM-2026-0002 (Meeting for 5 on 24 September at 3 pm (1.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 4 on 22 September at 10 am (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 4 - Date: 22 Sep…"
3. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 4 on 22 September at 10 am (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 10 am (setup 30m earlier) – 10 am + 2.0h (+1…"
4. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 24 September at 3 pm (1.0h) [ROOM-2026-0002]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 24 Sep…"
5. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 4 on 22 September at 10 am (2.0h) (ACTIVE, MEDIUM)
- ROOM-2026-0002: Meeting for 5 on 24 September at 3 pm (1.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 4 on 22 September at 10 am (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 4
- Date: 22 September
- Time: 10 am (2.0h)
- Meeting type: workshop
- Location preference: Corporate Office
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Catering / amenities: none
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 4 on 22 September at 10 am (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 10 am (setup 30m earlier) – 10 am + 2.0h (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 24 September at 3 pm (1.0h) [ROOM-2026-0002]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 24 September
- Time: 3 pm (1.0h)
- Meeting type: workshop
- Location preference: Corporate Office
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Catering / amenities: none
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0002
```

#### test_employee_satisfied_closes_operational — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 4 on tomorrow at 11 am (1.0h)) — closed.
2. It wrote to employee2@acme.demo. Subject: "Confirm Booking: Meeting for 4 on tomorrow at 11 am (1.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 2, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 4 - Date: tomorr…"
3. It wrote to employee2@acme.demo. Subject: "Booking Confirmed: Meeting for 4 on tomorrow at 11 am (1.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 2, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 11 am (setup 30m earlier) – 11 am + 1.0h (+1…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 4 on tomorrow at 11 am (1.0h) (CLOSED, MEDIUM)

Reply sent:

- To: employee2@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 4 on tomorrow at 11 am (1.0h) [ROOM-2026-0001]

```
Dear Employee 2,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 4
- Date: tomorrow
- Time: 11 am (1.0h)
- Meeting type: workshop
- Location preference: Corporate Office
- Catering / amenities: none
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee2@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 4 on tomorrow at 11 am (1.0h) [ROOM-2026-0001]

```
Dear Employee 2,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 11 am (setup 30m earlier) – 11 am + 1.0h (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
After the meeting, just reply "satisfied" and we'll close it off.
```

#### test_oversize_headcount_is_no_resource_and_emails — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h)) — still open.
2. It wrote to big.team@company.com. Subject: "No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, No room fits 80 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40 o…"
3. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

No room fits 80 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

### test_cloudmailin.py

5 cases, 0 failed.

#### test_normalize_cloudmailin_payload — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_continuation_uses_in_reply_to_thread — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_continuation_prefers_references_root_over_clarification_id — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Reply to our outbound clarification must stay on the original thread.

No email was stored for this case.

#### test_cloudmailin_ingest_idempotent — PASSED

What happened:

1. alice@example.com sent an email. Subject: "Meeting Room Request". They wrote: "Hi, I need a meeting room for 8 people tomorrow at 3 PM for 2 hours."
2. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: alice@example.com
- Subject: Meeting Room Request

```
Hi, I need a meeting room for 8 people tomorrow at 3 PM for 2 hours.
```

#### test_cloudmailin_webhook_endpoint — PASSED

What happened:

1. alice@example.com sent an email. Subject: "Meeting Room Request". They wrote: "Hi, I need a meeting room for 8 people tomorrow at 3 PM for 2 hours."
2. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: alice@example.com
- Subject: Meeting Room Request

```
Hi, I need a meeting room for 8 people tomorrow at 3 PM for 2 hours.
```

### test_desk_lifecycle.py

14 cases, 0 failed.

#### test_priority_rules_raise_for_safety_and_lower_for_no_rush — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_sla_is_the_tighter_of_department_and_priority — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_new_request_types_route_to_their_owning_team — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_non_returnable_gate_pass_needs_sign_off — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_urgent_safety_issue_is_dispatched_at_once_and_admin_alerted — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "urgent". They wrote: "socket near my desk is sparking, there is smoke!"
2. The desk opened TKT-2026-0001 (Sparking socket) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 8 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
4. It wrote to ops-desk@example.com. Subject: "Urgent: Sparking socket [TKT-2026-0001]". The message starts: "Dear Team, The following request is urgent and requires attention. Request: TKT-2026-0001 Subject: Sparking socket URGENT - safety / business-stopping signal: …"
5. It wrote to facilities@acme-real.com. Subject: "Work Order: Sparking socket [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Sparking socket Repair. No asset record matc…"
6. It wrote to arjun.singh@acme.demo. Subject: "Re: urgent [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
7. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Sparking socket (ACTIVE, URGENT, stage DISPATCHED, decision REPAIR_UNKNOWN)

Email received:

- From: arjun.singh@acme.demo
- Subject: urgent

```
socket near my desk is sparking, there is smoke!
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Urgent: Sparking socket [TKT-2026-0001]

```
Dear Team,

The following request is urgent and requires attention.

Request: TKT-2026-0001
Subject: Sparking socket

URGENT - safety / business-stopping signal: "sparking"

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Electrical
Team: Facilities & Maintenance
Priority: Urgent (safety / business-stopping signal: "sparking")

Details:
- Issue: socket sparking and smoke

Please reply "assign to <email>" to transfer it, "tell requester: <message>" to update the requester, "done - <note>" if it is already complete, or "cancel".

Regards,
Workplace Team
```

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Sparking socket [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Sparking socket

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 8

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Electrical
Team: Facilities & Maintenance
Priority: Urgent (safety / business-stopping signal: "sparking")
Due by: 18 Oct, 3:48 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Issue: socket sparking and smoke

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if th…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: urgent [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Please also provide:
- Where exactly (floor / area / desk)?

Regards,
Workplace Team
```

#### test_team_verbs_move_the_case_without_false_completion — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "chair". They wrote: "chair wheel broken in cabin 4"
2. facilities@acme-real.com sent an email. Subject: "Re: Work Order: Chair broken [TKT-2026-0001]". They wrote: "on it, technician coming in 30 mins"
3. facilities@acme-real.com sent an email. Subject: "Re: Work Order: Chair broken [TKT-2026-0001]". They wrote: "will be done tomorrow"
4. facilities@acme-real.com sent an email. Subject: "Re: Work Order: Chair broken [TKT-2026-0001]". They wrote: "issue: spare wheel not in stock, need vendor"
5. facilities@acme-real.com sent an email. Subject: "Re: Work Order: Chair broken [TKT-2026-0001]". They wrote: "done, wheel replaced"
6. The desk opened TKT-2026-0001 (Chair broken) — closed as done.
7. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
8. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Chair broken Repair This item. Repairs on re…"
9. It wrote to arjun.singh@acme.demo. Subject: "Re: chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
10. It wrote to arjun.singh@acme.demo. Subject: "chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Update on TKT-2026-0001 (Chair broken) from Facilities & Maintenance: on it, technician coming in 30 mins Regards, Workplace Team"
11. It wrote to ops-desk@example.com. Subject: "Ops Update: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair broken Facilities & Maintenance update: on it, technician coming in 30 mins …"
12. It wrote to arjun.singh@acme.demo. Subject: "chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Update on TKT-2026-0001 (Chair broken) from Facilities & Maintenance: will be done tomorrow Regards, Workplace Team"
13. It wrote to ops-desk@example.com. Subject: "Ops Update: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair broken Facilities & Maintenance update: will be done tomorrow Record check: …"
14. It wrote to ops-desk@example.com. Subject: "Ops Update: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, The following request is at risk of missing its due time. Request: TKT-2026-0001 Subject: Chair broken Facilities & Maintenance reports a problem: s…"
15. It wrote to arjun.singh@acme.demo. Subject: "chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, A quick update on TKT-2026-0001 (Chair broken): Facilities & Maintenance has hit a snag - spare wheel not in stock, need vendor We're on it a…"
16. It wrote to arjun.singh@acme.demo. Subject: "chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Good news - TKT-2026-0001 (Chair broken) has been taken care of. Note from Facilities & Maintenance: wheel replaced If anything is still not …"
17. It wrote to ops-desk@example.com. Subject: "Ops Update: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair broken Completed by Facilities & Maintenance: wheel replaced Record check: -…"
18. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair broken Thanks for completing this. To close it as verified, please reply wit…"
19. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Chair broken (RESOLVED, MEDIUM, stage RESOLVED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: chair

```
chair wheel broken in cabin 4
```

- From: facilities@acme-real.com
- Subject: Re: Work Order: Chair broken [TKT-2026-0001]

```
on it, technician coming in 30 mins
```

- From: facilities@acme-real.com
- Subject: Re: Work Order: Chair broken [TKT-2026-0001]

```
will be done tomorrow
```

- From: facilities@acme-real.com
- Subject: Re: Work Order: Chair broken [TKT-2026-0001]

```
issue: spare wheel not in stock, need vendor
```

- From: facilities@acme-real.com
- Subject: Re: Work Order: Chair broken [TKT-2026-0001]

```
done, wheel replaced
```

Reply sent:

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair broken [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Chair broken

Repair This item. Repairs on record: 0 of 6.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 4
- Issue: chair wheel broken

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <email>" to transfer the work…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Update on TKT-2026-0001 (Chair broken) from Facilities & Maintenance: on it, technician coming in 30 mins

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Chair broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair broken

Facilities & Maintenance update: on it, technician coming in 30 mins

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: cabin 4
- Issue: chair wheel broken


Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Update on TKT-2026-0001 (Chair broken) from Facilities & Maintenance: will be done tomorrow

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Chair broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair broken

Facilities & Maintenance update: will be done tomorrow

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: cabin 4
- Issue: chair wheel broken


Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Update: Chair broken [TKT-2026-0001]

```
Dear Team,

The following request is at risk of missing its due time.

Request: TKT-2026-0001
Subject: Chair broken

Facilities & Maintenance reports a problem: spare wheel not in stock, need vendor

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 4
- Issue: chair wheel broken

Please reply "assign to <email>" to transfer it, "tell requester: <message>" to update the requester, "done - <note>" if it is already complete, or "cancel".

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: chair [TKT-2026-0001]

```
Dear Arjun Singh,

A quick update on TKT-2026-0001 (Chair broken): Facilities & Maintenance has hit a snag - spare wheel not in stock, need vendor

We're on it and will update you as soon as it moves.

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Good news - TKT-2026-0001 (Chair broken) has been taken care of.
Note from Facilities & Maintenance: wheel replaced

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Chair broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair broken

Completed by Facilities & Maintenance: wheel replaced

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: cabin 4
- Issue: chair wheel broken


Regards,
Workplace Team
```

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair broken

Thanks for completing this. To close it as verified, please reply with what was fixed or done (a photo works too) (or attach a photo).

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: cabin 4
- Issue: chair wheel broken


Regards,
Workplace Team
```

#### test_requester_not_fixed_reopens_and_thanks_closes — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "chair". They wrote: "chair wheel broken in cabin 4"
2. facilities@acme-real.com sent an email. Subject: "Re: Work Order: Chair broken [TKT-2026-0001]". They wrote: "done"
3. arjun.singh@acme.demo sent an email. Subject: "Re: chair". They wrote: "still not working, the wheel came off again"
4. facilities@acme-real.com sent an email. Subject: "Re: Work Order: Chair broken [TKT-2026-0001]". They wrote: "done, fixed properly now"
5. arjun.singh@acme.demo sent an email. Subject: "Re: chair". They wrote: "thanks, all good now"
6. The desk opened TKT-2026-0001 (Chair broken) — closed.
7. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
8. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Chair broken Repair This item. Repairs on re…"
9. It wrote to arjun.singh@acme.demo. Subject: "Re: chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
10. It wrote to arjun.singh@acme.demo. Subject: "chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Good news - TKT-2026-0001 (Chair broken) has been taken care of. If anything is still not right, just reply "not fixed" and I'll reopen it. O…"
11. It wrote to ops-desk@example.com. Subject: "Ops Update: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair broken Completed by Facilities & Maintenance Record check: - Item: no matchi…"
12. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair broken Thanks for completing this. To close it as verified, please reply wit…"
13. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Chair broken Reopened - requester says it is…"
14. It wrote to arjun.singh@acme.demo. Subject: "Re: chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Request TKT-2026-0001 (Chair broken) has been reopened and returned to Facilities & Maintenance, together with your note. You will be updated…"
15. It wrote to arjun.singh@acme.demo. Subject: "chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Good news - TKT-2026-0001 (Chair broken) has been taken care of. Note from Facilities & Maintenance: fixed properly now If anything is still …"
16. It wrote to ops-desk@example.com. Subject: "Ops Update: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair broken Completed by Facilities & Maintenance: fixed properly now Record chec…"
17. It wrote to arjun.singh@acme.demo. Subject: "Re: chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Request TKT-2026-0001 has been closed. Thank you for confirming. Regards, Workplace Team"
18. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Chair broken (CLOSED, MEDIUM, stage CLOSED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: chair

```
chair wheel broken in cabin 4
```

- From: facilities@acme-real.com
- Subject: Re: Work Order: Chair broken [TKT-2026-0001]

```
done
```

- From: arjun.singh@acme.demo
- Subject: Re: chair

```
still not working, the wheel came off again
```

- From: facilities@acme-real.com
- Subject: Re: Work Order: Chair broken [TKT-2026-0001]

```
done, fixed properly now
```

- From: arjun.singh@acme.demo
- Subject: Re: chair

```
thanks, all good now
```

Reply sent:

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair broken [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Chair broken

Repair This item. Repairs on record: 0 of 6.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 4
- Issue: chair wheel broken

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <email>" to transfer the work…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Good news - TKT-2026-0001 (Chair broken) has been taken care of.

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Chair broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair broken

Completed by Facilities & Maintenance

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: cabin 4
- Issue: chair wheel broken


Regards,
Workplace Team
```

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair broken

Thanks for completing this. To close it as verified, please reply with what was fixed or done (a photo works too) (or attach a photo).

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: cabin 4
- Issue: chair wheel broken


Regards,
Workplace Team
```

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair broken [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Chair broken

Reopened - requester says it is not sorted (reopen #1)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 4
- Issue: chair wheel broken
- Requester note: still not working, the wheel came off again

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed …
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Request TKT-2026-0001 (Chair broken) has been reopened and returned to Facilities & Maintenance, together with your note. You will be updated on this thread.

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Good news - TKT-2026-0001 (Chair broken) has been taken care of.
Note from Facilities & Maintenance: fixed properly now

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Chair broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair broken

Completed by Facilities & Maintenance: fixed properly now

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: cabin 4
- Issue: chair wheel broken
- Requester note: still not working, the wheel came off again


Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Request TKT-2026-0001 has been closed. Thank you for confirming.

Regards,
Workplace Team
```

#### test_dashboard_approval_dispatches_a_desk_case — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "Need server room access"
2. The desk opened ITS-2026-0001 (Server room access) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 3 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to ops-desk@example.com. Subject: "Ops Decision: Server room access [ITS-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: ITS-2026-0001 Subject: Server room access Needs your approval - access card requests…"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [ITS-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged and sent for approval. Request: ITS-2026-0001 Subject: Server room access You will be updated on this thread onc…"
6. It wrote to ops-desk@example.com. Subject: "Ops Decision: Server room access [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Server room access Repair This item. Repairs…"
7. It wrote to arjun.singh@acme.demo. Subject: "Request [ITS-2026-0001]". The message starts: "Dear Arjun Singh, Request ITS-2026-0001 (Server room access) is approved and assigned to IT Support. You will be updated on this thread when the work is comple…"
8. It wrote to ops-desk@example.com. Subject: "Ops Decision: Server room access [ITS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ITS-2026-0001 Subject: Server room access Approved via dashboard by admin@prototype.local Record check: -…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Server room access (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
Need server room access
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Server room access [ITS-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: ITS-2026-0001
Subject: Server room access

Needs your approval - access card requests need admin sign-off

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 3

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Access card / ID
Team: IT Support

Details:
- Area: server room

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [ITS-2026-0001]

```
Dear Arjun Singh,

Your request has been logged and sent for approval.

Request: ITS-2026-0001
Subject: Server room access

You will be updated on this thread once a decision is recorded.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Server room access [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Server room access

Repair This item. Repairs on record: 0 of 3.
(No IT Support contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 3

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Access card / ID
Team: IT Support
Due by: 18 Oct, 7:48 AM

Details:
- Area: server room

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <the card number issued or access granted>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The requ…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Request [ITS-2026-0001]

```
Dear Arjun Singh,

Request ITS-2026-0001 (Server room access) is approved and assigned to IT Support. You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Decision: Server room access [ITS-2026-0001]

```
Dear Team,

Please note the following update.

Request: ITS-2026-0001
Subject: Server room access

Approved via dashboard by admin@prototype.local

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 3

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Access card / ID
Team: IT Support
Due by: 18 Oct, 7:48 AM

Details:
- Area: server room


Regards,
Workplace Team
```

#### test_sweep_reminds_then_escalates_once — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "chair". They wrote: "chair wheel broken in cabin 4"
2. The desk opened TKT-2026-0001 (Chair broken) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Chair broken Repair This item. Repairs on re…"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
6. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Chair broken Reminder - due by 18 Oct, 7:48 …"
7. It wrote to ops-desk@example.com. Subject: "Escalation: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, The following request has been escalated and requires attention. Request: TKT-2026-0001 Subject: Chair broken SLA missed - Facilities & Maintenance …"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Chair broken (AT_RISK, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: chair

```
chair wheel broken in cabin 4
```

Reply sent:

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair broken [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Chair broken

Repair This item. Repairs on record: 0 of 6.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 4
- Issue: chair wheel broken

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <email>" to transfer the work…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair broken [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Chair broken

Reminder - due by 18 Oct, 7:48 AM. Reply "on it", "issue: <what is blocking>" or "done".

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 4
- Issue: chair wheel broken

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>…
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Escalation: Chair broken [TKT-2026-0001]

```
Dear Team,

The following request has been escalated and requires attention.

Request: TKT-2026-0001
Subject: Chair broken

SLA missed - Facilities & Maintenance has not closed this (1h overdue)
No timely team progress on TKT-2026-0001. Stage=DISPATCHED. Approved alternatives: CleanSupply Partners. Reassignment needs facilities/admin approval.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 4
- Issue: chair wheel broken

Please reply "assign to <email>" to transfer it, "tell requester: <message>" to update …
```

#### test_sweep_nudges_requester_then_closes_politely — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "need a cab to airport"
2. The desk opened TRV-2026-0001 (Cab to airport) — closed because nobody replied.
3. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [TRV-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged. Request: TRV-2026-0001 Subject: Cab to airport Please reply with the following: - When do you need to travel (d…"
4. It wrote to arjun.singh@acme.demo. Subject: "Request [TRV-2026-0001]". The message starts: "Dear Arjun Singh, Just checking in on TRV-2026-0001 (Cab to airport) - I still need: - When do you need to travel (date and time)? Reply here and I'll take it …"
5. It wrote to arjun.singh@acme.demo. Subject: "Request [TRV-2026-0001]". The message starts: "Dear Arjun Singh, I haven't heard back on TRV-2026-0001 (Cab to airport), so I've closed it for now. Just reply here whenever you're ready and I'll pick it up …"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TRV-2026-0001: Cab to airport (CANCELLED, MEDIUM, stage CLOSED_NO_REPLY)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
need a cab to airport
```

Reply sent:

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [TRV-2026-0001]

```
Dear Arjun Singh,

Your request has been logged.

Request: TRV-2026-0001
Subject: Cab to airport

Please reply with the following:
- When do you need to travel (date and time)?

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Request [TRV-2026-0001]

```
Dear Arjun Singh,

Just checking in on TRV-2026-0001 (Cab to airport) - I still need:
- When do you need to travel (date and time)?

Reply here and I'll take it forward straight away.

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Request [TRV-2026-0001]

```
Dear Arjun Singh,

I haven't heard back on TRV-2026-0001 (Cab to airport), so I've closed it for now. Just reply here whenever you're ready and I'll pick it up again.

Regards,
Workplace Team
```

#### test_sweep_reminds_approver_and_auto_closes_resolved — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "Request". They wrote: "Need server room access"
2. arjun.singh@acme.demo sent an email. Subject: "chair". They wrote: "chair wheel broken in cabin 4"
3. facilities@acme-real.com sent an email. Subject: "Re: Work Order: Chair broken [TKT-2026-0001]". They wrote: "done"
4. The desk opened ITS-2026-0001 (Server room access) — waiting for approval; TKT-2026-0001 (Chair broken) — closed.
5. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 3 repairs. The records did not call for a replacement, so this stayed a normal repair.
6. It wrote to ops-desk@example.com. Subject: "Ops Decision: Server room access [ITS-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: ITS-2026-0001 Subject: Server room access Needs your approval - access card requests…"
7. It wrote to arjun.singh@acme.demo. Subject: "Re: Request [ITS-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged and sent for approval. Request: ITS-2026-0001 Subject: Server room access You will be updated on this thread onc…"
8. It wrote to ops-desk@example.com. Subject: "Ops Decision: Server room access [ITS-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: ITS-2026-0001 Subject: Server room access Reminder - still waiting for your approval…"
9. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Chair broken Repair This item. Repairs on re…"
10. It wrote to arjun.singh@acme.demo. Subject: "Re: chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
11. It wrote to arjun.singh@acme.demo. Subject: "chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Good news - TKT-2026-0001 (Chair broken) has been taken care of. If anything is still not right, just reply "not fixed" and I'll reopen it. O…"
12. It wrote to ops-desk@example.com. Subject: "Ops Update: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair broken Completed by Facilities & Maintenance Record check: - Item: no matchi…"
13. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Chair broken Thanks for completing this. To close it as verified, please reply wit…"
14. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Server room access (AT_RISK, MEDIUM, stage AWAITING_APPROVAL, decision REPAIR)
- TKT-2026-0001: Chair broken (CLOSED, MEDIUM, stage CLOSED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: Request

```
Need server room access
```

- From: arjun.singh@acme.demo
- Subject: chair

```
chair wheel broken in cabin 4
```

- From: facilities@acme-real.com
- Subject: Re: Work Order: Chair broken [TKT-2026-0001]

```
done
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Server room access [ITS-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: ITS-2026-0001
Subject: Server room access

Needs your approval - access card requests need admin sign-off

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 3

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Access card / ID
Team: IT Support

Details:
- Area: server room

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Request [ITS-2026-0001]

```
Dear Arjun Singh,

Your request has been logged and sent for approval.

Request: ITS-2026-0001
Subject: Server room access

You will be updated on this thread once a decision is recorded.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Server room access [ITS-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: ITS-2026-0001
Subject: Server room access

Reminder - still waiting for your approval (access card requests need admin sign-off)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 3

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Access card / ID
Team: IT Support

Details:
- Area: server room

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair broken [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Chair broken

Repair This item. Repairs on record: 0 of 6.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 4
- Issue: chair wheel broken

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <email>" to transfer the work…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Good news - TKT-2026-0001 (Chair broken) has been taken care of.

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Chair broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair broken

Completed by Facilities & Maintenance

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: cabin 4
- Issue: chair wheel broken


Regards,
Workplace Team
```

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair broken [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Chair broken

Thanks for completing this. To close it as verified, please reply with what was fixed or done (a photo works too) (or attach a photo).

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: cabin 4
- Issue: chair wheel broken


Regards,
Workplace Team
```

#### test_email_dropped_mid_processing_is_picked_up_again_once — PASSED

What happened:

1. stuck.user@acme.demo sent an email. Subject: "hi". They wrote: "Hi"
2. fresh.user@acme.demo sent an email. Subject: "hi". They wrote: "Hi again"
3. It wrote to stuck.user@acme.demo. Subject: "Re: hi". The message starts: "Hi Stuck, Good to hear from you! This is the Admin Desk - I can help with repairs and facility issues, IT help, housekeeping, visitor passes, parking, gate pas…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: stuck.user@acme.demo
- Subject: hi

```
Hi
```

- From: fresh.user@acme.demo
- Subject: hi

```
Hi again
```

Reply sent:

- To: stuck.user@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: hi

```
Hi Stuck,

Good to hear from you! This is the Admin Desk - I can help with repairs and facility issues, IT help, housekeeping, visitor passes, parking, gate passes, couriers, office supplies, travel and cabs, seating, events, onboarding and meeting rooms.

How can I help you today? Just reply with what you need.

Workplace Team
```

#### test_times_keep_their_minutes — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_kpis_and_list_are_type_neutral — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "chair". They wrote: "chair wheel broken in cabin 4"
2. The desk opened TKT-2026-0001 (Chair broken) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to facilities@acme-real.com. Subject: "Work Order: Chair broken [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Chair broken Repair This item. Repairs on re…"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: chair [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Chair broken (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: chair

```
chair wheel broken in cabin 4
```

Reply sent:

- To: facilities@acme-real.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Chair broken [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Chair broken

Repair This item. Repairs on record: 0 of 6.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Maintenance
Team: Facilities & Maintenance
Due by: 18 Oct, 7:48 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: cabin 4
- Issue: chair wheel broken

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <email>" to transfer the work…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair [TKT-2026-0001]

```
Dear Arjun Singh,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

### test_email_provider.py

10 cases, 0 failed.

#### test_factory_defaults_to_cloudmailin — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_normalize_graph_message_shape — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_oauth_url_requires_client_id — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_oauth_url_includes_personal_tenant — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_scopes_exclude_mail_readwrite — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_outlook_source_idempotent_poll — PASSED

What happened:

1. employee1@acme.demo sent an email. Subject: "Need a meeting room for 8 people tomorrow at 3 PM for 2 hours". They wrote: "Hi, I need a meeting room for 8 people tomorrow at 3 PM for 2 hours."
2. The desk opened ROOM-2026-0001 (Meeting for 8 on tomorrow at 3 pm (2.0h)) — still open.
3. It wrote to employee1@acme.demo. Subject: "Information required: Meeting for 8 on tomorrow at 3 pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Thanks for your meeting-room request — it's registered as ROOM-2026-0001. Here's what I have so far: - Attendees: 8 - Date: tomorrow - Time: 3…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 8 on tomorrow at 3 pm (2.0h) (ACTIVE, MEDIUM)

Email received:

- From: employee1@acme.demo
- Subject: Need a meeting room for 8 people tomorrow at 3 PM for 2 hours

```
Hi, I need a meeting room for 8 people tomorrow at 3 PM for 2 hours.
```

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_REQUIRED
- Subject: Information required: Meeting for 8 on tomorrow at 3 pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Thanks for your meeting-room request — it's registered as ROOM-2026-0001.

Here's what I have so far:

- Attendees: 8
- Date: tomorrow
- Time: 3 pm (2.0h)

To lock in a room I just need:

- Which office or building is required? Your primary office is Corporate Office, Gurugram.
- Meeting type: internal, client/vendor, interview, training, confidential, or other?

Also worth a quick check:

- Hybrid / AV: not answered
- Presentation display: not answered
- Catering / amenities: not answered
- Special access / security: not answered
- Confidentiality: not answered

Meanwhile I've provisionally held Focus Room 5A until 18 Oct, 11:48 PM so it isn't taken while you reply.

Just reply to this email with the details.
```

#### test_same_thread_reply_merges_conversation — PASSED

What happened:

1. employee4@acme.demo sent an email. Subject: "Need a room for 15 people". They wrote: "I need a room/resources for tomorrow for 15 people."
2. employee4@acme.demo sent an email. Subject: "Re: Need a room". They wrote: "2 PM to 4 PM."
3. The desk opened ROOM-2026-0001 (Meeting for 15 on tomorrow at 2 PM–4 PM. (2.0h)) — still open.
4. It wrote to employee4@acme.demo. Subject: "Information required: Request registered — details needed [ROOM-2026-0001]". The message starts: "Dear Employee 4, Thanks for your meeting-room request — it's registered as ROOM-2026-0001. Here's what I have so far: - Attendees: 15 - Date: tomorrow To lock …"
5. It wrote to employee4@acme.demo. Subject: "Information required: Additional details needed [ROOM-2026-0001]". The message starts: "Dear Employee 4, Here's what I have so far: - Attendees: 15 - Date: tomorrow - Time: 2 PM – 4 PM. - Location preference: Corporate Office, Gurugram To lock in …"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 15 on tomorrow at 2 PM–4 PM. (2.0h) (ACTIVE, MEDIUM)

Email received:

- From: employee4@acme.demo
- Subject: Need a room for 15 people

```
I need a room/resources for tomorrow for 15 people.
```

- From: employee4@acme.demo
- Subject: Re: Need a room

```
2 PM to 4 PM.
```

Reply sent:

- To: employee4@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_REQUIRED
- Subject: Information required: Request registered — details needed [ROOM-2026-0001]

```
Dear Employee 4,

Thanks for your meeting-room request — it's registered as ROOM-2026-0001.

Here's what I have so far:

- Attendees: 15
- Date: tomorrow

To lock in a room I just need:

- What time slot do you need (e.g. 10:00 AM–1:00 PM, or 2:00 PM for 1 hour)?
- Which office or building is required? Your primary office is Corporate Office, Gurugram.
- Meeting type: internal, client/vendor, interview, training, confidential, or other?

Also worth a quick check:

- Hybrid / AV: not answered
- Presentation display: not answered
- Catering / amenities: not answered
- Special access / security: not answered
- Confidentiality: not answered

Just reply to this email with the details.
```

- To: employee4@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_REQUIRED
- Subject: Information required: Additional details needed [ROOM-2026-0001]

```
Dear Employee 4,

Here's what I have so far:

- Attendees: 15
- Date: tomorrow
- Time: 2 PM – 4 PM.
- Location preference: Corporate Office, Gurugram

To lock in a room I just need:

- Meeting type: internal, client/vendor, interview, training, confidential, or other?

Also worth a quick check:

- Hybrid / AV: not answered
- Presentation display: not answered
- Catering / amenities: not answered
- Special access / security: not answered
- Confidentiality: not answered

Meanwhile I've provisionally held Conference Room 8B until 18 Oct, 11:48 PM so it isn't taken while you reply.

Just reply to this email with the details.
```

#### test_clarification_calls_send_reply — PASSED

What happened:

1. employee4@acme.demo sent an email. Subject: "Need a room". They wrote: "I need a meeting room tomorrow."
2. The desk opened ROOM-2026-0001 (Need a room) — still open.
3. It wrote to employee4@acme.demo. Subject: "Information required: Request registered — details needed [ROOM-2026-0001]". The message starts: "Dear Employee 4, Thanks for your meeting-room request — it's registered as ROOM-2026-0001. Here's what I have so far: - Date: tomorrow To lock in a room I just…"
4. It wrote to employee4@acme.demo. Subject: "Information required: Additional details needed [CASE-TEST]". The message starts: "Dear Employee 4, To lock in a room I just need: - How many attendees? - Preferred time? - Duration? Just reply to this email with the details."
5. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Need a room (ACTIVE, MEDIUM)

Email received:

- From: employee4@acme.demo
- Subject: Need a room

```
I need a meeting room tomorrow.
```

Reply sent:

- To: employee4@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_REQUIRED
- Subject: Information required: Request registered — details needed [ROOM-2026-0001]

```
Dear Employee 4,

Thanks for your meeting-room request — it's registered as ROOM-2026-0001.

Here's what I have so far:

- Date: tomorrow

To lock in a room I just need:

- How many people will attend in person?
- What time slot do you need (e.g. 10:00 AM–1:00 PM, or 2:00 PM for 1 hour)?
- Which office or building is required? Your primary office is Corporate Office, Gurugram.
- Meeting type: internal, client/vendor, interview, training, confidential, or other?

Also worth a quick check:

- Hybrid / AV: not answered
- Presentation display: not answered
- Catering / amenities: not answered
- Special access / security: not answered
- Confidentiality: not answered

Just reply to this email with the details.
```

- To: employee4@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_REQUIRED
- Subject: Information required: Additional details needed [CASE-TEST]

```
Dear Employee 4,

To lock in a room I just need:

- How many attendees?
- Preferred time?
- Duration?

Just reply to this email with the details.
```

#### test_fetch_skips_known_ids — PASSED

What happened:

1. a@b.com sent an email. Subject: "old". They wrote: "old"
2. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: a@b.com
- Subject: old

```
old
```

#### test_send_reply_uses_graph_reply_endpoint — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_enterprise_v3.py

8 cases, 0 failed.

#### test_context_gateway_tools — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_ai_governance_blocks_emergency — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_commercial_cost_reported_not_paid — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- FAC-TEST-1: AC fix (IN_PROGRESS, MEDIUM)

No email was stored for this case.

#### test_contract_amend_and_terminate — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_vendor_workspace_and_sealed_rfq — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_meter_rollover_carbon_waste — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_governed_learning_requires_corrections — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_outbox_dlq_requeue — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_event_services.py

16 cases, 4 failed.

#### test_included_services_need_no_approval_and_close_financially — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 6 on 28th october at 3 pm–5pm (2.0h)) — closed.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Focus Room 5A (seats 8) Your booking: - Attendees: 6 - Date: 28th octob…"
3. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Focus Room 5A Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release) Ac…"
4. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Focus Room 5A [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Focus Room 5A Requester: employee1@acme.demo When: Wed 28 Oct 2026, 3 pm–5pm · Corporate O…"
5. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) (CLOSED, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Focus Room 5A (seats 8)

Your booking:
- Attendees: 6
- Date: 28th october
- Time: 3 pm – 5pm
- Meeting type: team review
- Hybrid / AV: no
- Presentation display: yes
- Location preference: Corporate Office
- Catering / amenities: tea and coffee
- Dietary: all veg
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Focus Room 5A
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

Active preparations: catering, AV/display.
No separate approval is needed for meeting room, tea / coffee (vending and pantry), drinking water and standard bottles, installed AV / VC and internal IT support.
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Focus Room 5A [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Focus Room 5A

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Focus Room 5A (8 seats), setup 30 min before
People: 6

To arrange:
- Display / screen
- Tea and coffee — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Focus Room 5A after the meeting
- IT / AV: with you (no IT Support mailbox set yet)
    · Display / projector working
    · AV test done by 28 Oct, 2:30 PM
- Cafeteria: with you (no Cafeteria & Catering mailbox set yet)
    · Tea / coffee (vending and pantry): 6 people
    · Dietary…
```

#### test_approval_covers_only_the_chargeable_part — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 10 on 28th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Meeting Room 5C (seats 10) Your booking: - Attendees: 10 - Date: 28th o…"
3. It wrote to mgr@example.com. Subject: "Approval Required: Approval needed — catering spend [ROOM-2026-0001]". The message starts: "ROOM-2026-0001 — Meeting for 10 on 28th october at 3 pm–5pm (2.0h) Approval needed (catering spend) — only for the chargeable part of this request. Requester: …"
4. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Meeting Room 5C Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release) …"
5. It wrote to ops-desk@example.com. Subject: "Ops Decision: Booking confirmed — Meeting Room 5C [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Meeting Room 5C Requester: employee1@acme.demo When: Wed 28 Oct 2026, 3 pm–5pm · Corporate…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Meeting Room 5C (seats 10)

Your booking:
- Attendees: 10
- Date: 28th october
- Time: 3 pm – 5pm
- Meeting type: team review
- Hybrid / AV: no
- Location preference: Corporate Office
- Catering / amenities: high tea and coffee
- Dietary: all veg
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: mgr@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Approval Required: Approval needed — catering spend [ROOM-2026-0001]

```
ROOM-2026-0001 — Meeting for 10 on 28th october at 3 pm–5pm (2.0h)

Approval needed (catering spend) — only for the chargeable part of this request.

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Meeting Room 5C (10 seats) — booked
People: 10

Cost centre: EN-2101 (Engineering)
Chargeable:
- High tea / snacks (special menu): 10 people x Rs 450 = Rs 4,500 (contract rate)
Estimated chargeable total: Rs 4,500 before tax
Included at no incremental charge: meeting room, tea / coffee (vending and pantry), drinking water and standard bottles.

Reply "approve" or "reject, <reason>". Included site services go ahead without this approval.
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Meeting Room 5C
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

Active preparations: catering.
No separate approval is needed for meeting room, tea / coffee (vending and pantry), drinking water and standard bottles. Cost approval will cover only high tea / snacks (special menu).
The chargeable items are waiting for cost approval — everything else goes ahead now, and I'll confirm once it's approved.

When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Booking confirmed — Meeting Room 5C [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Meeting Room 5C

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Meeting Room 5C (10 seats), setup 30 min before
People: 10

To arrange:
- High tea and coffee — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Meeting Room 5C after the meeting
- Cafeteria: with you (no Cafeteria & Catering mailbox set yet)
    · High tea / snacks (special menu): 10 people — on hold until cost approval (we'll confirm)
    · Tea / coffee (vending and pantry): 10 people
    · Dietary: all veg
When the items with you…
```

#### test_real_department_gets_its_list_and_done_marks_ready — FAILED

What happened:

1. cafe@example.com sent an email. Subject: "Re: [ACTION REQUIRED] [ROOM-2026-0001] tasks". They wrote: "done"
2. ops-desk@example.com sent an email. Subject: "Re: [ACTION REQUIRED] [ROOM-2026-0001] tasks". They wrote: "done"
3. The desk opened ROOM-2026-0001 (Meeting for 6 on 28th october at 3 pm–5pm (2.0h)) — still open.
4. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 6 - Date: 28th o…"
5. It wrote to cafe@example.com. Subject: "Action Required: Cafeteria tasks — Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "ROOM-2026-0001 — Meeting for 6 on 28th october at 3 pm–5pm (2.0h) When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office Room: Huddle Room F2-R2 (setup from 3 pm (…"
6. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release…"
7. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Huddle Room F2-R2 Requester: employee1@acme.demo When: Wed 28 Oct 2026, 3 pm–5pm · Corpora…"
8. It wrote to cafe@example.com. Subject: "Update Noted: Cafeteria — marked ready [ROOM-2026-0001]". The message starts: "Marked Cafeteria as ready. Case: ROOM-2026-0001"
9. It wrote to ops-desk@example.com. Subject: "Update Noted: Administration — marked ready [ROOM-2026-0001]". The message starts: "Marked Administration as ready. Case: ROOM-2026-0001"
10. It wrote to employee1@acme.demo. Subject: "Ready: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Everything for your meeting is ready. Room: Huddle Room F2-R2 When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office Confirmed ready: - Administra…"
11. Result: this test failed. The replies above were still written, and the failure is noted at the end of this case.


Case state:

- ROOM-2026-0001: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Email received:

- From: cafe@example.com
- Subject: Re: [ACTION REQUIRED] [ROOM-2026-0001] tasks

```
done
```

- From: ops-desk@example.com
- Subject: Re: [ACTION REQUIRED] [ROOM-2026-0001] tasks

```
done
```

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 6
- Date: 28th october
- Time: 3 pm – 5pm
- Meeting type: team review
- Hybrid / AV: no
- Location preference: Corporate Office
- Catering / amenities: lunch
- Dietary: all veg
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: cafe@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Action Required: Cafeteria tasks — Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
ROOM-2026-0001 — Meeting for 6 on 28th october at 3 pm–5pm (2.0h)

When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (setup from 3 pm (setup 30m earlier), release by 5pm (+15m release))
People: 6

Cafeteria:
- Working lunch (sponsored cafeteria meal): 6 people — cost approved
- Dietary: all veg

Ready by: 28 Oct, 2:30 PM
Reply "done" when everything above is ready, or "issue: <what's blocking>" if something can't be delivered.
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

Active preparations: catering.
No separate approval is needed for meeting room, drinking water and standard bottles. Cost approval will cover only working lunch (sponsored cafeteria meal).

When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 6

To arrange:
- Lunch — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
- Cafeteria: sent to cafe@example.com
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

- To: cafe@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Update Noted: Cafeteria — marked ready [ROOM-2026-0001]

```
Marked Cafeteria as ready.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Update Noted: Administration — marked ready [ROOM-2026-0001]

```
Marked Administration as ready.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ready: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Everything for your meeting is ready.

Room: Huddle Room F2-R2
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office

Confirmed ready:
- Administration: Drinking water in the room; Orchestrator role: module_helper; Spine template: MEETING_ROOM
- Cafeteria: Working lunch (sponsored cafeteria meal): 6 people — cost approved; Dietary: all veg

Approved chargeable items: Working lunch (sponsored cafeteria meal).

After the meeting I'll check with you that everything was delivered as planned.

Case: ROOM-2026-0001
```

Failure:

```
E   assert False
     +  where False = any(<generator object test_real_department_gets_its_list_and_done_marks_ready.<locals>.<genexpr> at 0x00000233913F4930>)
```

#### test_department_issue_raises_at_risk — PASSED

What happened:

1. cafe@example.com sent an email. Subject: "Re: [ACTION REQUIRED] [ROOM-2026-0001] tasks". They wrote: "Sorry, we are short of staff that day and can't serve lunch"
2. The desk opened ROOM-2026-0001 (Meeting for 6 on 28th october at 3 pm–5pm (2.0h)) — still open.
3. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 6 - Date: 28th o…"
4. It wrote to cafe@example.com. Subject: "Action Required: Cafeteria tasks — Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "ROOM-2026-0001 — Meeting for 6 on 28th october at 3 pm–5pm (2.0h) When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office Room: Huddle Room F2-R2 (setup from 3 pm (…"
5. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release…"
6. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Huddle Room F2-R2 Requester: employee1@acme.demo When: Wed 28 Oct 2026, 3 pm–5pm · Corpora…"
7. It wrote to ops-desk@example.com. Subject: "At Risk: Cafeteria — "Sorry, we are short of staff that day and can't serve lunch" (from [ROOM-2026-0001]". The message starts: "ROOM-2026-0001 — Meeting for 6 on 28th october at 3 pm–5pm (2.0h) Blocker: Cafeteria — "Sorry, we are short of staff that day and can't serve lunch" (from cafe…"
8. It wrote to cafe@example.com. Subject: "Update Noted: Cafeteria — issue logged [ROOM-2026-0001]". The message starts: "Logged the issue on Cafeteria; the admin has been alerted. Case: ROOM-2026-0001"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Email received:

- From: cafe@example.com
- Subject: Re: [ACTION REQUIRED] [ROOM-2026-0001] tasks

```
Sorry, we are short of staff that day and can't serve lunch
```

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 6
- Date: 28th october
- Time: 3 pm – 5pm
- Meeting type: team review
- Hybrid / AV: no
- Location preference: Corporate Office
- Catering / amenities: lunch
- Dietary: all veg
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: cafe@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Action Required: Cafeteria tasks — Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
ROOM-2026-0001 — Meeting for 6 on 28th october at 3 pm–5pm (2.0h)

When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (setup from 3 pm (setup 30m earlier), release by 5pm (+15m release))
People: 6

Cafeteria:
- Working lunch (sponsored cafeteria meal): 6 people — cost approved
- Dietary: all veg

Ready by: 28 Oct, 2:30 PM
Reply "done" when everything above is ready, or "issue: <what's blocking>" if something can't be delivered.
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

Active preparations: catering.
No separate approval is needed for meeting room, drinking water and standard bottles. Cost approval will cover only working lunch (sponsored cafeteria meal).

When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 6

To arrange:
- Lunch — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
- Cafeteria: sent to cafe@example.com
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To change the booking, please reply, for example "move to 3pm", "make it 20 people", or "cancel".
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: At Risk: Cafeteria — "Sorry, we are short of staff that day and can't serve lunch" (from [ROOM-2026-0001]

```
ROOM-2026-0001 — Meeting for 6 on 28th october at 3 pm–5pm (2.0h)

Blocker: Cafeteria — "Sorry, we are short of staff that day and can't serve lunch" (from cafe@example.com)
Deadline: ready by 28 Oct, 2:30 PM
Impact: Cafeteria items may not be ready for the meeting on 28th october.
Required action: Arrange an alternative or tell the requester; the owner replies "done" once it's sorted.

Reply with what to do — e.g. "tell requester: <message>", "approve", "cancel" — and I'll carry it out.
```

- To: cafe@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Update Noted: Cafeteria — issue logged [ROOM-2026-0001]

```
Logged the issue on Cafeteria; the admin has been alerted.

Case: ROOM-2026-0001
```

#### test_admin_reject_is_not_read_as_a_package_issue — PASSED

What happened:

1. ops-desk@example.com sent an email. Subject: "Re: [ACTION REQUIRED] [ROOM-2026-0001] tasks". They wrote: "reject, we can't fund snacks this month"
2. The desk opened ROOM-2026-0001 (Meeting for 10 on 28th october at 3 pm–5pm (2.0h)) — still open.
3. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Meeting Room 5C (seats 10) Your booking: - Attendees: 10 - Date: 28th o…"
4. It wrote to mgr@example.com. Subject: "Approval Required: Approval needed — catering spend [ROOM-2026-0001]". The message starts: "ROOM-2026-0001 — Meeting for 10 on 28th october at 3 pm–5pm (2.0h) Approval needed (catering spend) — only for the chargeable part of this request. Requester: …"
5. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Meeting Room 5C Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release) …"
6. It wrote to ops-desk@example.com. Subject: "Ops Decision: Booking confirmed — Meeting Room 5C [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Meeting Room 5C Requester: employee1@acme.demo When: Wed 28 Oct 2026, 3 pm–5pm · Corporate…"
7. It wrote to ops-desk@example.com. Subject: "Ops Update: Task list updated after a change [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Task list updated after a change Requester: employee1@acme.demo When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Of…"
8. It wrote to employee1@acme.demo. Subject: "Ops Update: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your cost for high tea / snacks (special menu) request was not approved by ops. Reason: we can't fund snacks this month Your room booking itse…"
9. It wrote to ops-desk@example.com. Subject: "Ops Done: REJECT: Rejected: cost for high tea / snacks (special menu). Requester informed. [ROOM-2026-0001]". The message starts: "Done — Rejected: cost for high tea / snacks (special menu). Requester informed. Case: ROOM-2026-0001"
10. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Email received:

- From: ops-desk@example.com
- Subject: Re: [ACTION REQUIRED] [ROOM-2026-0001] tasks

```
reject, we can't fund snacks this month
```

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Meeting Room 5C (seats 10)

Your booking:
- Attendees: 10
- Date: 28th october
- Time: 3 pm – 5pm
- Meeting type: team review
- Hybrid / AV: no
- Location preference: Corporate Office
- Catering / amenities: high tea
- Dietary: all veg
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: mgr@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Approval Required: Approval needed — catering spend [ROOM-2026-0001]

```
ROOM-2026-0001 — Meeting for 10 on 28th october at 3 pm–5pm (2.0h)

Approval needed (catering spend) — only for the chargeable part of this request.

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Meeting Room 5C (10 seats) — booked
People: 10

Cost centre: EN-2101 (Engineering)
Chargeable:
- High tea / snacks (special menu): 10 people x Rs 450 = Rs 4,500 (contract rate)
Estimated chargeable total: Rs 4,500 before tax
Included at no incremental charge: meeting room, tea / coffee (vending and pantry), drinking water and standard bottles.

Reply "approve" or "reject, <reason>". Included site services go ahead without this approval.
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Meeting Room 5C
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

Active preparations: catering.
No separate approval is needed for meeting room, tea / coffee (vending and pantry), drinking water and standard bottles. Cost approval will cover only high tea / snacks (special menu).
The chargeable items are waiting for cost approval — everything else goes ahead now, and I'll confirm once it's approved.

When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Booking confirmed — Meeting Room 5C [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Meeting Room 5C

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Meeting Room 5C (10 seats), setup 30 min before
People: 10

To arrange:
- High tea — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Meeting Room 5C after the meeting
- Cafeteria: with you (no Cafeteria & Catering mailbox set yet)
    · High tea / snacks (special menu): 10 people — on hold until cost approval (we'll confirm)
    · Tea / coffee (vending and pantry): 10 people
    · Dietary: all veg
When the items with you are ready,…
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Task list updated after a change [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Task list updated after a change

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Meeting Room 5C (10 seats), setup 30 min before
People: 10

To arrange:
- High tea — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Meeting Room 5C after the meeting
- Cafeteria: with you (no Cafeteria & Catering mailbox set yet)
    · High tea / snacks (special menu): 10 people — cost not approved, do not arrange
    · Tea / coffee (vending and pantry): 10 people
    · Dietary: all veg
When the items with you are ready, reply "done"…
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your cost for high tea / snacks (special menu) request was not approved by ops. Reason: we can't fund snacks this month

Your room booking itself is unaffected.

Case: ROOM-2026-0001
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Done: REJECT: Rejected: cost for high tea / snacks (special menu). Requester informed. [ROOM-2026-0001]

```
Done — Rejected: cost for high tea / snacks (special menu). Requester informed.

Case: ROOM-2026-0001
```

#### test_pending_approval_gets_one_reminder_then_one_escalation — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 10 on 28th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Meeting Room 5C (seats 10) Your booking: - Attendees: 10 - Date: 28th o…"
3. It wrote to mgr@example.com. Subject: "Approval Required: Approval needed — catering spend [ROOM-2026-0001]". The message starts: "ROOM-2026-0001 — Meeting for 10 on 28th october at 3 pm–5pm (2.0h) Approval needed (catering spend) — only for the chargeable part of this request. Requester: …"
4. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Meeting Room 5C Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release) …"
5. It wrote to ops-desk@example.com. Subject: "Ops Decision: Booking confirmed — Meeting Room 5C [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Meeting Room 5C Requester: employee1@acme.demo When: Wed 28 Oct 2026, 3 pm–5pm · Corporate…"
6. It wrote to mgr@example.com. Subject: "Approval Required: Reminder: Approval needed — catering spend [ROOM-2026-0001]". The message starts: "ROOM-2026-0001 — Meeting for 10 on 28th october at 3 pm–5pm (2.0h) Reminder: this approval is still pending and the chargeable items are on hold. Approval need…"
7. It wrote to ops-desk@example.com. Subject: "At Risk: Cost approval still pending [ROOM-2026-0001]". The message starts: "ROOM-2026-0001 — Meeting for 10 on 28th october at 3 pm–5pm (2.0h) Blocker: Cost approval still pending Deadline: ready by 28 Oct, 2:30 PM Impact: Chargeable i…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Meeting Room 5C (seats 10)

Your booking:
- Attendees: 10
- Date: 28th october
- Time: 3 pm – 5pm
- Meeting type: team review
- Hybrid / AV: no
- Location preference: Corporate Office
- Catering / amenities: high tea
- Dietary: all veg
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: mgr@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Approval Required: Approval needed — catering spend [ROOM-2026-0001]

```
ROOM-2026-0001 — Meeting for 10 on 28th october at 3 pm–5pm (2.0h)

Approval needed (catering spend) — only for the chargeable part of this request.

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Meeting Room 5C (10 seats) — booked
People: 10

Cost centre: EN-2101 (Engineering)
Chargeable:
- High tea / snacks (special menu): 10 people x Rs 450 = Rs 4,500 (contract rate)
Estimated chargeable total: Rs 4,500 before tax
Included at no incremental charge: meeting room, tea / coffee (vending and pantry), drinking water and standard bottles.

Reply "approve" or "reject, <reason>". Included site services go ahead without this approval.
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Meeting Room 5C
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

Active preparations: catering.
No separate approval is needed for meeting room, tea / coffee (vending and pantry), drinking water and standard bottles. Cost approval will cover only high tea / snacks (special menu).
The chargeable items are waiting for cost approval — everything else goes ahead now, and I'll confirm once it's approved.

When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Booking confirmed — Meeting Room 5C [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Meeting Room 5C

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Meeting Room 5C (10 seats), setup 30 min before
People: 10

To arrange:
- High tea — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Meeting Room 5C after the meeting
- Cafeteria: with you (no Cafeteria & Catering mailbox set yet)
    · High tea / snacks (special menu): 10 people — on hold until cost approval (we'll confirm)
    · Tea / coffee (vending and pantry): 10 people
    · Dietary: all veg
When the items with you are ready,…
```

- To: mgr@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Approval Required: Reminder: Approval needed — catering spend [ROOM-2026-0001]

```
ROOM-2026-0001 — Meeting for 10 on 28th october at 3 pm–5pm (2.0h)

Reminder: this approval is still pending and the chargeable items are on hold.

Approval needed (catering spend) — only for the chargeable part of this request.

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Meeting Room 5C (10 seats) — booked
People: 10

Cost centre: EN-2101 (Engineering)
Chargeable:
- High tea / snacks (special menu): 10 people x Rs 450 = Rs 4,500 (contract rate)
Estimated chargeable total: Rs 4,500 before tax
Included at no incremental charge: meeting room, tea / coffee (vending and pantry), drinking water and standard bottles.

Reply "approve" or "reject, <reason>". Included site services go ahead without this approval.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: At Risk: Cost approval still pending [ROOM-2026-0001]

```
ROOM-2026-0001 — Meeting for 10 on 28th october at 3 pm–5pm (2.0h)

Blocker: Cost approval still pending
Deadline: ready by 28 Oct, 2:30 PM
Impact: Chargeable items (High tea / snacks (special menu)) can't be arranged.
Required action: Approver: reply "approve" or "reject, <reason>" on the approval mail (or use its links).

Reply with what to do — e.g. "tell requester: <message>", "approve", "cancel" — and I'll carry it out.
```

#### test_service_entry_then_matching_invoice_closes_financially — FAILED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 6 on 28th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 6 - Date: 28th o…"
3. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release…"
4. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Huddle Room F2-R2 Requester: employee1@acme.demo When: Wed 28 Oct 2026, 3 pm–5pm · Corpora…"
5. It wrote to employee1@acme.demo. Subject: "Completed: Please confirm delivery [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting in Huddle Room F2-R2 has ended. How did it go? Just reply with one of these: - Fully delivered - Partially delivered, and what wa…"
6. Result: this test failed. The replies above were still written, and the failure is noted at the end of this case.


Case state:

- ROOM-2026-0001: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 6
- Date: 28th october
- Time: 3 pm – 5pm
- Meeting type: team review
- Hybrid / AV: no
- Location preference: Corporate Office
- Catering / amenities: lunch
- Dietary: all veg
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

Active preparations: catering.
No separate approval is needed for meeting room, drinking water and standard bottles. Cost approval will cover only working lunch (sponsored cafeteria meal).

When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 6

To arrange:
- Lunch — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
- Cafeteria: with you (no Cafeteria & Catering mailbox set yet)
    · Working lunch (sponsored cafeteria meal): 6 people — cost approved
    · Dietary: all veg
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To…
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Completed: Please confirm delivery [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting in Huddle Room F2-R2 has ended. How did it go? Just reply with one of these:

- Fully delivered
- Partially delivered, and what was short
- Issue reported, and what went wrong

After that I'll ask you to confirm the chargeable quantities so billing matches what was delivered.

Case: ROOM-2026-0001
```

Failure:

```
E   assert False
     +  where False = any(<generator object _completed_lunch_case.<locals>.<genexpr> at 0x000002338F8D3AC0>)
```

#### test_service_entry_variance_and_invoice_mismatch_are_billing_exceptions — FAILED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 6 on 28th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 6 - Date: 28th o…"
3. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release…"
4. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Huddle Room F2-R2 Requester: employee1@acme.demo When: Wed 28 Oct 2026, 3 pm–5pm · Corpora…"
5. It wrote to employee1@acme.demo. Subject: "Completed: Please confirm delivery [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting in Huddle Room F2-R2 has ended. How did it go? Just reply with one of these: - Fully delivered - Partially delivered, and what wa…"
6. Result: this test failed. The replies above were still written, and the failure is noted at the end of this case.


Case state:

- ROOM-2026-0001: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 6
- Date: 28th october
- Time: 3 pm – 5pm
- Meeting type: team review
- Hybrid / AV: no
- Location preference: Corporate Office
- Catering / amenities: lunch
- Dietary: all veg
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

Active preparations: catering.
No separate approval is needed for meeting room, drinking water and standard bottles. Cost approval will cover only working lunch (sponsored cafeteria meal).

When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 6

To arrange:
- Lunch — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
- Cafeteria: with you (no Cafeteria & Catering mailbox set yet)
    · Working lunch (sponsored cafeteria meal): 6 people — cost approved
    · Dietary: all veg
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To…
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Completed: Please confirm delivery [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting in Huddle Room F2-R2 has ended. How did it go? Just reply with one of these:

- Fully delivered
- Partially delivered, and what was short
- Issue reported, and what went wrong

After that I'll ask you to confirm the chargeable quantities so billing matches what was delivered.

Case: ROOM-2026-0001
```

Failure:

```
E   assert False
     +  where False = any(<generator object _completed_lunch_case.<locals>.<genexpr> at 0x000002338F7D5220>)
```

#### test_invoice_mail_quoting_the_case_is_matched — FAILED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 6 on 28th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 6 - Date: 28th o…"
3. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release…"
4. It wrote to ops-desk@example.com. Subject: "Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Huddle Room F2-R2 Requester: employee1@acme.demo When: Wed 28 Oct 2026, 3 pm–5pm · Corpora…"
5. It wrote to employee1@acme.demo. Subject: "Completed: Please confirm delivery [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting in Huddle Room F2-R2 has ended. How did it go? Just reply with one of these: - Fully delivered - Partially delivered, and what wa…"
6. Result: this test failed. The replies above were still written, and the failure is noted at the end of this case.


Case state:

- ROOM-2026-0001: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 6
- Date: 28th october
- Time: 3 pm – 5pm
- Meeting type: team review
- Hybrid / AV: no
- Location preference: Corporate Office
- Catering / amenities: lunch
- Dietary: all veg
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

Active preparations: catering.
No separate approval is needed for meeting room, drinking water and standard bottles. Cost approval will cover only working lunch (sponsored cafeteria meal).

When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Booking confirmed — Huddle Room F2-R2 [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Huddle Room F2-R2

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Huddle Room F2-R2 (6 seats), setup 30 min before
People: 6

To arrange:
- Lunch — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Huddle Room F2-R2 after the meeting
- Cafeteria: with you (no Cafeteria & Catering mailbox set yet)
    · Working lunch (sponsored cafeteria meal): 6 people — cost approved
    · Dietary: all veg
When the items with you are ready, reply "done" (or "issue: <what's blocking>").

No action is required. To…
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Completed: Please confirm delivery [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting in Huddle Room F2-R2 has ended. How did it go? Just reply with one of these:

- Fully delivered
- Partially delivered, and what was short
- Issue reported, and what went wrong

After that I'll ask you to confirm the chargeable quantities so billing matches what was delivered.

Case: ROOM-2026-0001
```

Failure:

```
E   assert False
     +  where False = any(<generator object _completed_lunch_case.<locals>.<genexpr> at 0x000002338F61F780>)
```

#### test_two_day_training_books_both_days_and_plans_travel — PASSED

What happened:

1. The desk opened TRG-2026-0001 (Meeting for 18 on 2026-10-20 at 9:30 am–5:30 pm (8.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 18 on 2026-10-20 at 9:30 am–5:30 pm (8.0h) [TRG-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Learning Studio A (seats 30) Held on all 2 days: 2026-10-20, 2026-10-21…"
3. It wrote to mgr@example.com. Subject: "Approval Required: Approval needed — event cost [TRG-2026-0001]". The message starts: "TRG-2026-0001 — Meeting for 18 on 2026-10-20 at 9:30 am–5:30 pm (8.0h) Approval needed (event cost) — only for the chargeable part of this request. Requester: …"
4. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 18 on 2026-10-20 at 9:30 am–5:30 pm (8.0h) [TRG-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Learning Studio A Case: TRG-2026-0001 Hold window: 9:30 am (setup 60m earlier) – 5:30 pm (+30m r…"
5. It wrote to ops-desk@example.com. Subject: "Ops Decision: Booking confirmed — Learning Studio A [TRG-2026-0001]". The message starts: "Dear Colleague, Request: TRG-2026-0001 Subject: Booking confirmed — Learning Studio A Requester: employee1@acme.demo When: Tue 20 Oct 2026, 9:30 am–5:30 pm · C…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TRG-2026-0001: Meeting for 18 on 2026-10-20 at 9:30 am–5:30 pm (8.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 18 on 2026-10-20 at 9:30 am–5:30 pm (8.0h) [TRG-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Learning Studio A (seats 30)
Held on all 2 days: 2026-10-20, 2026-10-21
Layout: classroom
It's bigger than you need, but it's the best free fit for that time.

Your booking:
- Attendees: 18
- Date: 2026-10-20
- Time: 9:30 am – 5:30 pm
- Meeting type: sales training
- Hybrid / AV: no
- Location preference: Corporate Office
- Catering / amenities: none
- Dietary: all veg
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: TRG-2026-0001
```

- To: mgr@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Approval Required: Approval needed — event cost [TRG-2026-0001]

```
TRG-2026-0001 — Meeting for 18 on 2026-10-20 at 9:30 am–5:30 pm (8.0h)

Approval needed (event cost) — only for the chargeable part of this request.

Requester: employee1@acme.demo
When: Tue 20 Oct 2026, 9:30 am–5:30 pm · Corporate Office
Room: Learning Studio A (30 seats) — booked
People: 18

Cost centre: EN-2101 (Engineering)
Chargeable:
- Flight (empanelled travel agent): 1 people x Rs 12,000 = Rs 12,000
- Hotel (empanelled): 2 room-nights x Rs 4,500 = Rs 9,000
- Airport / station transfer: 2 trips x Rs 1,500 = Rs 3,000
Estimated chargeable total: Rs 24,000 before tax
Included at no incremental charge: meeting room, installed AV / VC and internal IT support, standard stationery and printing.

Reply "approve" or "reject, <reason>". Included site services go ahead without this approval.
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 18 on 2026-10-20 at 9:30 am–5:30 pm (8.0h) [TRG-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Learning Studio A
Case: TRG-2026-0001
Hold window: 9:30 am (setup 60m earlier) – 5:30 pm (+30m release)

No visitor, parking, catering or billing modules were activated.
Days: 2026-10-20, 2026-10-21 (same room every day)
Layout: classroom
Travel: 1 traveller(s) — the travel desk has been asked to arrange it
No separate approval is needed for meeting room, installed AV / VC and internal IT support, standard stationery and printing. Cost approval will cover only flight (empanelled travel agent), hotel (empanelled), airport / station transfer.
The chargeable items are waiting for cost approval — everything else goes ahead now, and I'll confirm once it's approved.

When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
- Names and arrival/departure details of the travellin…
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Booking confirmed — Learning Studio A [TRG-2026-0001]

```
Dear Colleague,

Request: TRG-2026-0001
Subject: Booking confirmed — Learning Studio A

Requester: employee1@acme.demo
When: Tue 20 Oct 2026, 9:30 am–5:30 pm · Corporate Office
Room: Learning Studio A (30 seats), setup 60 min before
People: 18

To arrange:
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Set up Learning Studio A in classroom layout for 19 (includes 1 trainer seat) on each day: Tue 20 Oct, Wed 21 Oct
    · Standard stationery and printing
    · Attendance sheet / capture at the entrance
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Learning Studio A after the meeting
- IT / AV: with you (no IT Support mailbox set yet)
    · Display / projector working
    · Trainer la…
```

#### test_training_room_is_kept_for_training — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 25 on 28th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 25 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Auditorium A (seats 40) It's bigger than you need, but it's the best fr…"
3. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 25 on 28th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 25 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Auditorium A (seats 40)
It's bigger than you need, but it's the best free fit for that time.

Your booking:
- Attendees: 25
- Date: 28th october
- Time: 3 pm – 5pm
- Meeting type: internal meeting
- Hybrid / AV: no
- Location preference: Corporate Office
- Catering / amenities: none
- Dietary: all veg
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

#### test_room_is_held_while_details_are_pending_and_lapses_quietly — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- ROOM-2026-0001: Meeting for 6 on 28th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

No email was stored for this case.

#### test_day_of_month_is_not_taken_as_a_start_time — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_setup_site_services_and_cost_centres — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_signed_link_approves_once — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 10 on 28th october at 3 pm–5pm (2.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Meeting Room 5C (seats 10) Your booking: - Attendees: 10 - Date: 28th o…"
3. It wrote to mgr@example.com. Subject: "Approval Required: Approval needed — catering spend [ROOM-2026-0001]". The message starts: "ROOM-2026-0001 — Meeting for 10 on 28th october at 3 pm–5pm (2.0h) Approval needed (catering spend) — only for the chargeable part of this request. Requester: …"
4. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Meeting Room 5C Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release) …"
5. It wrote to ops-desk@example.com. Subject: "Ops Decision: Booking confirmed — Meeting Room 5C [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Booking confirmed — Meeting Room 5C Requester: employee1@acme.demo When: Wed 28 Oct 2026, 3 pm–5pm · Corporate…"
6. It wrote to ops-desk@example.com. Subject: "Ops Update: Task list updated after cost approval [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Task list updated after cost approval Requester: employee1@acme.demo When: Wed 28 Oct 2026, 3 pm–5pm · Corpora…"
7. It wrote to ops-desk@example.com. Subject: "Ops Update: Cost for high tea / snacks (special menu): approved (signed link) [ROOM-2026-0001]". The message starts: "Dear Colleague, Request: ROOM-2026-0001 Subject: Cost for high tea / snacks (special menu): approved (signed link) Requester: employee1@acme.demo When: Wed 28 …"
8. It wrote to employee1@acme.demo. Subject: "Update: Cost approved [ROOM-2026-0001]". The message starts: "Dear Employee 1, Approved: cost for high tea / snacks (special menu). We're arranging it now. Case: ROOM-2026-0001"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Meeting Room 5C (seats 10)

Your booking:
- Attendees: 10
- Date: 28th october
- Time: 3 pm – 5pm
- Meeting type: team review
- Hybrid / AV: no
- Location preference: Corporate Office
- Catering / amenities: high tea
- Dietary: all veg
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Presentation display: no
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: mgr@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Approval Required: Approval needed — catering spend [ROOM-2026-0001]

```
ROOM-2026-0001 — Meeting for 10 on 28th october at 3 pm–5pm (2.0h)

Approval needed (catering spend) — only for the chargeable part of this request.

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Meeting Room 5C (10 seats) — booked
People: 10

Cost centre: EN-2101 (Engineering)
Chargeable:
- High tea / snacks (special menu): 10 people x Rs 450 = Rs 4,500 (contract rate)
Estimated chargeable total: Rs 4,500 before tax
Included at no incremental charge: meeting room, tea / coffee (vending and pantry), drinking water and standard bottles.

Approve: https://ops.example.com/api/v1/public/approvals/apr_d159494c4ef3/approve?exp=1792520331&sig=83a75dee30d74def0c8bc3f3361bbeaad8ad138b&for=ops-desk%40example.com
Reject: https://ops.example.com/api/v1/public/approvals/apr_d159494c4ef3/reject?exp=1792520331&sig=58b5bd998627fd54228a4758af7a5e4f78b4f71d&for=o…
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 10 on 28th october at 3 pm–5pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Meeting Room 5C
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 5pm (+15m release)

Active preparations: catering.
No separate approval is needed for meeting room, tea / coffee (vending and pantry), drinking water and standard bottles. Cost approval will cover only high tea / snacks (special menu).
The chargeable items are waiting for cost approval — everything else goes ahead now, and I'll confirm once it's approved.

When you have them, please also send:
- Cost centre and approving department head (for the chargeable items).
After the meeting, just reply "satisfied" and we'll close it off.
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Booking confirmed — Meeting Room 5C [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Booking confirmed — Meeting Room 5C

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Meeting Room 5C (10 seats), setup 30 min before
People: 10

To arrange:
- High tea — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Meeting Room 5C after the meeting
- Cafeteria: with you (no Cafeteria & Catering mailbox set yet)
    · High tea / snacks (special menu): 10 people — on hold until cost approval (we'll confirm)
    · Tea / coffee (vending and pantry): 10 people
    · Dietary: all veg
When the items with you are ready,…
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Task list updated after cost approval [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Task list updated after cost approval

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Meeting Room 5C (10 seats), setup 30 min before
People: 10

To arrange:
- High tea — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Meeting Room 5C after the meeting
- Cafeteria: with you (no Cafeteria & Catering mailbox set yet)
    · High tea / snacks (special menu): 10 people — cost approved
    · Tea / coffee (vending and pantry): 10 people
    · Dietary: all veg
When the items with you are ready, reply "done" (or "issue: <w…
```

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Cost for high tea / snacks (special menu): approved (signed link) [ROOM-2026-0001]

```
Dear Colleague,

Request: ROOM-2026-0001
Subject: Cost for high tea / snacks (special menu): approved (signed link)

Requester: employee1@acme.demo
When: Wed 28 Oct 2026, 3 pm–5pm · Corporate Office
Room: Meeting Room 5C (10 seats), setup 30 min before
People: 10

To arrange:
- High tea — all veg
- Orchestrator role: module_helper
- Spine template: MEETING_ROOM

Task lists by owner:
- Administration: with you (no Admin & Workplace mailbox set yet)
    · Drinking water in the room
    · Orchestrator role: module_helper
    · Spine template: MEETING_ROOM
    · Final room inspection before setup time
    · Clean and reset Meeting Room 5C after the meeting
- Cafeteria: with you (no Cafeteria & Catering mailbox set yet)
    · High tea / snacks (special menu): 10 people — cost approved
    · Tea / coffee (vending and pantry): 10 people
    · Dietary: all veg
When the items with you are ready,…
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Update: Cost approved [ROOM-2026-0001]

```
Dear Employee 1,

Approved: cost for high tea / snacks (special menu). We're arranging it now.

Case: ROOM-2026-0001
```

#### test_reject_link_cannot_be_reused_for_approve — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_facilities_enterprise.py

7 cases, 0 failed.

#### test_location_profile_and_space_master — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_service_catalogue_and_work_order — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_asset_completeness_and_amc_call — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_inventory_entitlement_cycle_expiry — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_budget_commit_accrual_transfer_chargeback — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_compliance_bcp_incident_fanout_soft_ses — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_pm_job_plan — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_gmail_admin_loops.py

9 cases, 0 failed.

#### test_wants_flight_detects_travel_asks — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_search_flights_schedule_only_no_auto_fare — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_parse_travel_date_and_iata — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_old_link_flight_options_are_not_usable — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_pick_realistic_fare_ignores_india_teaser_list_price — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_department_autocode_from_name_and_place — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_plus_tag_team_email_rejected — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_stock_below_min_opens_bulk_reorder — PASSED

What happened:

1. The desk opened SUP-2026-0001 (Stock reorder: Stapler×24, Pen box×10) — handed to the team and still open.
2. It wrote to orders@officemart.test. Subject: "Stock reorder: Stapler×24, Pen box×10 [SUP-2026-0001]". The message starts: "Dear Team, Stock is below the reorder minimum. Please arrange supply of the following in one delivery. Request: SUP-2026-0001 - Stapler (STAPLER): order 24 eac…"
3. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- SUP-2026-0001: Stock reorder: Stapler×24, Pen box×10 (ACTIVE, MEDIUM, stage DISPATCHED)

Reply sent:

- To: orders@officemart.test
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Stock reorder: Stapler×24, Pen box×10 [SUP-2026-0001]

```
Dear Team,

Stock is below the reorder minimum. Please arrange supply of the following in one delivery.

Request: SUP-2026-0001

- Stapler (STAPLER): order 24 each (on hand 3, min 4)
- Pen box (PEN_BOX): order 10 each (on hand 2, min 3)

Please reply "Done" when the goods are shipped, or "Confirm received" with the quantities, so the stock record for this location can be updated.

Regards,
Workplace Team
```

#### test_parse_qty — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_live_directory.py

22 cases, 0 failed.

#### test_onboarding_from_hr_runs_end_to_end — PASSED

What happened:

1. kshitiz.vishwakarma2003@gmail.com sent an email. Subject: "New joinee - Naman Kumar". They wrote: "Hi team, Please arrange onboarding for our new joinee. Employee name: Naman Kumar Joining date: 21 October 2026 Department: Marketing 1. Laptop with Office and…"
2. it.servicess8989@gmail.com sent an email. Subject: "Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". They wrote: "laptop is being imaged, will be done by evening"
3. flexxftw12@gmail.com sent an email. Subject: "Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". They wrote: "desk is ready, 3F-12"
4. it.servicess8989@gmail.com sent an email. Subject: "Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". They wrote: "everything is arranged, will hand over the laptop and card when he joins"
5. it.servicess8989@gmail.com sent an email. Subject: "Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". They wrote: "laptop and card handed over"
6. flexxftw12@gmail.com sent an email. Subject: "Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". They wrote: "he is seated at 3F-12"
7. The desk opened ONB-2026-0001 (Onboarding for Naman Kumar) — closed as done.
8. It checked the records. Nothing in the records blocked it, so the desk carried on.
9. It wrote to it.servicess8989@gmail.com. Subject: "Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar New joiner onboar…"
10. It wrote to flexxftw12@gmail.com. Subject: "Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar New joiner onboar…"
11. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "Re: New joinee - Naman Kumar [ONB-2026-0001]". The message starts: "Hi Kshitiz, Day-1 note for Naman Kumar (you can forward this): - Report on 21 October 2026 at the office reception by 9:30 AM with a government photo ID. - HR …"
12. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "New joinee - Naman Kumar [ONB-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, Update on ONB-2026-0001 (Onboarding for Naman Kumar) from IT Support: Laptop is being imaged, ready by evening Regards, Workplace Team"
13. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar IT Support update: Laptop is being imaged, ready by eve…"
14. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "New joinee - Naman Kumar [ONB-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, Progress on ONB-2026-0001 (Onboarding for Naman Kumar): Facilities & Maintenance has finished their part. - A desk near the marketing…"
15. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar Facilities & Maintenance done - still waiting on IT Sup…"
16. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "New joinee - Naman Kumar [ONB-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, Everything for Naman Kumar is ready ahead of the joining day (21 Oct 2026) - ONB-2026-0001: - IT Support: Laptop with Office and VPN;…"
17. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar Ready for joining on 21 Oct 2026 - handover check on th…"
18. It wrote to it.servicess8989@gmail.com. Subject: "Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar Naman Kumar joins…"
19. It wrote to flexxftw12@gmail.com. Subject: "Work Order: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar Naman Kumar joins…"
20. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "New joinee - Naman Kumar [ONB-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, Naman Kumar joins today (ONB-2026-0001). I've asked IT Support, Facilities & Maintenance to confirm the handover and will update you …"
21. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "New joinee - Naman Kumar [ONB-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, Progress on ONB-2026-0001 (Onboarding for Naman Kumar): IT Support has finished their part. - Laptop with Office and VPN - Access car…"
22. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar IT Support done - still waiting on Facilities & Mainten…"
23. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "New joinee - Naman Kumar [ONB-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, Good news - ONB-2026-0001 (Onboarding for Naman Kumar) has been taken care of. Note from Facilities & Maintenance: Seated at desk 3F-…"
24. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: Onboarding for Naman Kumar [ONB-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ONB-2026-0001 Subject: Onboarding for Naman Kumar Completed - Facilities & Maintenance finished the last …"
25. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ONB-2026-0001: Onboarding for Naman Kumar (RESOLVED, MEDIUM, stage RESOLVED, decision PROCEED)

Email received:

- From: kshitiz.vishwakarma2003@gmail.com
- Subject: New joinee - Naman Kumar

```
Hi team,

Please arrange onboarding for our new joinee.

Employee name: Naman Kumar
Joining date: 21 October 2026
Department: Marketing

1. Laptop with Office and VPN
2. Access card
3. A desk near the marketing team

Regards,
Kshitiz (HR)
```

- From: it.servicess8989@gmail.com
- Subject: Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
laptop is being imaged, will be done by evening
```

- From: flexxftw12@gmail.com
- Subject: Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
desk is ready, 3F-12
```

- From: it.servicess8989@gmail.com
- Subject: Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
everything is arranged, will hand over the laptop and card when he joins
```

- From: it.servicess8989@gmail.com
- Subject: Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
laptop and card handed over
```

- From: flexxftw12@gmail.com
- Subject: Re: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
he is seated at 3F-12
```

Reply sent:

- To: it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

New joiner onboarding - IT Support tasks

Tasks assigned:
1. Laptop with Office and VPN
2. Access card

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Due by: 18 Oct, 11:49 PM

Details:
- Employee name: Naman Kumar
- Joining date: 21 October 2026
- Department: Marketing

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
If the team, type, or priority i…
```

- To: flexxftw12@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

New joiner onboarding - Facilities & Maintenance tasks

Tasks assigned:
1. A desk near the marketing team

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Due by: 18 Oct, 11:49 PM

Details:
- Employee name: Naman Kumar
- Joining date: 21 October 2026
- Department: Marketing

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
If the team, type, or priorit…
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: New joinee - Naman Kumar [ONB-2026-0001]

```
Hi Kshitiz,

Day-1 note for Naman Kumar (you can forward this):
- Report on 21 October 2026 at the office reception by 9:30 AM with a government photo ID.
- HR will meet you at reception for joining formalities.
- Your laptop, login, desk and ID / access card will be ready on day one.

Thanks - onboarding for Naman Kumar on 21 October 2026 is under way (ONB-2026-0001).

Best regards,
Workplace Team
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: New joinee - Naman Kumar [ONB-2026-0001]

```
Dear Kshitiz Vishwakarma,

Update on ONB-2026-0001 (Onboarding for Naman Kumar) from IT Support: Laptop is being imaged, ready by evening

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

Please note the following update.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

IT Support update: Laptop is being imaged, ready by evening

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Due by: 18 Oct, 11:49 PM

Details:
- Employee name: Naman Kumar
- Joining date: 21 October 2026
- Department: Marketing


Regards,
Workplace Team
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: New joinee - Naman Kumar [ONB-2026-0001]

```
Dear Kshitiz Vishwakarma,

Progress on ONB-2026-0001 (Onboarding for Naman Kumar): Facilities & Maintenance has finished their part.
- A desk near the marketing team
Note from the team: Desk 3F-12 is ready

Still in progress: IT Support.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

Please note the following update.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

Facilities & Maintenance done - still waiting on IT Support (Desk 3F-12 is ready)

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Due by: 18 Oct, 11:49 PM

Details:
- Employee name: Naman Kumar
- Joining date: 21 October 2026
- Department: Marketing


Regards,
Workplace Team
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: New joinee - Naman Kumar [ONB-2026-0001]

```
Dear Kshitiz Vishwakarma,

Everything for Naman Kumar is ready ahead of the joining day (21 Oct 2026) - ONB-2026-0001:
- IT Support: Laptop with Office and VPN; Access card (note: Laptop and card ready - handover when he joins)
- Facilities & Maintenance: A desk near the marketing team (note: Desk 3F-12 is ready)

On 21 Oct 2026 I'll ask the teams to confirm they've handed everything over to Naman Kumar, and I'll confirm here once that's done.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

Please note the following update.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

Ready for joining on 21 Oct 2026 - handover check on the day (Laptop and card ready - handover when he joins)

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Due by: 21 Oct, 6:00 PM

Details:
- Employee name: Naman Kumar
- Joining date: 21 October 2026
- Department: Marketing


Regards,
Workplace Team
```

- To: it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

Naman Kumar joins today. Please hand everything over and reply "handed over" (or "issue: <what is blocking>").

Tasks assigned:
1. Laptop with Office and VPN
2. Access card

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Due by: 21 Oct, 6:00 PM

Details:
- Employee name: Naman Kumar
- Joining date: 21 October 2026
- Department: Marketing

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detai…
```

- To: flexxftw12@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

Naman Kumar joins today. Please hand everything over and reply "handed over" (or "issue: <what is blocking>").

Tasks assigned:
1. A desk near the marketing team

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Due by: 21 Oct, 6:00 PM

Details:
- Employee name: Naman Kumar
- Joining date: 21 October 2026
- Department: Marketing

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <valu…
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: New joinee - Naman Kumar [ONB-2026-0001]

```
Dear Kshitiz Vishwakarma,

Naman Kumar joins today (ONB-2026-0001). I've asked IT Support, Facilities & Maintenance to confirm the handover and will update you here once it's done.

Regards,
Workplace Team
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: New joinee - Naman Kumar [ONB-2026-0001]

```
Dear Kshitiz Vishwakarma,

Progress on ONB-2026-0001 (Onboarding for Naman Kumar): IT Support has finished their part.
- Laptop with Office and VPN
- Access card
Note from the team: Laptop and access card handed over

Still in progress: Facilities & Maintenance.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

Please note the following update.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

IT Support done - still waiting on Facilities & Maintenance (Laptop and access card handed over)

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Due by: 21 Oct, 6:00 PM

Details:
- Employee name: Naman Kumar
- Joining date: 21 October 2026
- Department: Marketing


Regards,
Workplace Team
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: New joinee - Naman Kumar [ONB-2026-0001]

```
Dear Kshitiz Vishwakarma,

Good news - ONB-2026-0001 (Onboarding for Naman Kumar) has been taken care of.
Note from Facilities & Maintenance: Seated at desk 3F-12

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Onboarding for Naman Kumar [ONB-2026-0001]

```
Dear Team,

Please note the following update.

Request: ONB-2026-0001
Subject: Onboarding for Naman Kumar

Completed - Facilities & Maintenance finished the last part: Seated at desk 3F-12

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: New joiner onboarding
Teams working on it: IT Support, Facilities & Maintenance
Due by: 21 Oct, 6:00 PM

Details:
- Employee name: Naman Kumar
- Joining date: 21 October 2026
- Department: Marketing


Regards,
Workplace Team
```

#### test_updates_to_a_team_reply_to_the_previous_mail — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "AC issue". They wrote: "AC not cooling at 4th floor near pantry"
2. The desk opened TKT-2026-0001 (AC not cooling on 4th floor) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to flexxftw12@gmail.com. Subject: "Work Order: AC not cooling on 4th floor [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: AC not cooling on 4th floor Repair This item…"
5. It wrote to rohan.mehta@acme.demo. Subject: "Re: AC issue [TKT-2026-0001]". The message starts: "Dear Rohan Mehta, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
6. It wrote to flexxftw12@gmail.com. Subject: "Work Order: AC not cooling on 4th floor [TKT-2026-0001]". The message starts: "update 0"
7. It wrote to flexxftw12@gmail.com. Subject: "Work Order: AC not cooling on 4th floor [TKT-2026-0001]". The message starts: "update 1"
8. It wrote to flexxftw12@gmail.com. Subject: "Work Order: AC not cooling on 4th floor [TKT-2026-0001]". The message starts: "update 2"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: AC not cooling on 4th floor (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: rohan.mehta@acme.demo
- Subject: AC issue

```
AC not cooling at 4th floor near pantry
```

Reply sent:

- To: flexxftw12@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: AC not cooling on 4th floor [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: AC not cooling on 4th floor

Repair This item. Repairs on record: 0 of 6.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Air conditioning
Team: Facilities & Maintenance
Due by: 18 Oct, 7:49 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: 4th floor near pantry

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <email>" to transfer th…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: AC issue [TKT-2026-0001]

```
Dear Rohan Mehta,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: flexxftw12@gmail.com
- From: orchestration@adminservices.in
- Type: INFORMATION_ONLY
- Subject: Work Order: AC not cooling on 4th floor [TKT-2026-0001]

```
update 0
```

- To: flexxftw12@gmail.com
- From: orchestration@adminservices.in
- Type: INFORMATION_ONLY
- Subject: Work Order: AC not cooling on 4th floor [TKT-2026-0001]

```
update 1
```

- To: flexxftw12@gmail.com
- From: orchestration@adminservices.in
- Type: INFORMATION_ONLY
- Subject: Work Order: AC not cooling on 4th floor [TKT-2026-0001]

```
update 2
```

#### test_reply_chain_uses_the_message_id_recipients_see — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_ac_complaint_goes_to_facilities_and_back — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "AC issue". They wrote: "AC not cooling at 4th floor near pantry"
2. flexxftw12@gmail.com sent an email. Subject: "Re: Work Order: AC not cooling on 4th floor [TKT-2026-0001]". They wrote: "technician will reach in 30 mins"
3. flexxftw12@gmail.com sent an email. Subject: "Re: Work Order: AC not cooling on 4th floor [TKT-2026-0001]". They wrote: "gas refilled, cooling fine now"
4. The desk opened TKT-2026-0001 (AC not cooling on 4th floor) — closed as done.
5. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
6. It wrote to flexxftw12@gmail.com. Subject: "Work Order: AC not cooling on 4th floor [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: AC not cooling on 4th floor Repair This item…"
7. It wrote to rohan.mehta@acme.demo. Subject: "Re: AC issue [TKT-2026-0001]". The message starts: "Dear Rohan Mehta, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
8. It wrote to rohan.mehta@acme.demo. Subject: "AC issue [TKT-2026-0001]". The message starts: "Dear Rohan Mehta, Update on TKT-2026-0001 (AC not cooling on 4th floor) from Facilities & Maintenance: Technician arriving in 30 minutes Regards, Workplace Team"
9. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: AC not cooling on 4th floor [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: AC not cooling on 4th floor Facilities & Maintenance update: Technician arriving i…"
10. It wrote to rohan.mehta@acme.demo. Subject: "AC issue [TKT-2026-0001]". The message starts: "Dear Rohan Mehta, Good news - TKT-2026-0001 (AC not cooling on 4th floor) has been taken care of. Note from Facilities & Maintenance: Gas refilled, cooling res…"
11. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: AC not cooling on 4th floor [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: AC not cooling on 4th floor Completed by Facilities & Maintenance: Gas refilled, c…"
12. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: AC not cooling on 4th floor (RESOLVED, MEDIUM, stage RESOLVED, decision REPAIR)

Email received:

- From: rohan.mehta@acme.demo
- Subject: AC issue

```
AC not cooling at 4th floor near pantry
```

- From: flexxftw12@gmail.com
- Subject: Re: Work Order: AC not cooling on 4th floor [TKT-2026-0001]

```
technician will reach in 30 mins
```

- From: flexxftw12@gmail.com
- Subject: Re: Work Order: AC not cooling on 4th floor [TKT-2026-0001]

```
gas refilled, cooling fine now
```

Reply sent:

- To: flexxftw12@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: AC not cooling on 4th floor [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: AC not cooling on 4th floor

Repair This item. Repairs on record: 0 of 6.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Air conditioning
Team: Facilities & Maintenance
Due by: 18 Oct, 7:49 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: 4th floor near pantry
- Issue: AC not cooling

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: AC issue [TKT-2026-0001]

```
Dear Rohan Mehta,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: AC issue [TKT-2026-0001]

```
Dear Rohan Mehta,

Update on TKT-2026-0001 (AC not cooling on 4th floor) from Facilities & Maintenance: Technician arriving in 30 minutes

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: AC not cooling on 4th floor [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: AC not cooling on 4th floor

Facilities & Maintenance update: Technician arriving in 30 minutes

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Air conditioning
Team: Facilities & Maintenance
Due by: 18 Oct, 7:49 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: 4th floor near pantry
- Issue: AC not cooling


Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: AC issue [TKT-2026-0001]

```
Dear Rohan Mehta,

Good news - TKT-2026-0001 (AC not cooling on 4th floor) has been taken care of.
Note from Facilities & Maintenance: Gas refilled, cooling restored

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: AC not cooling on 4th floor [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: AC not cooling on 4th floor

Completed by Facilities & Maintenance: Gas refilled, cooling restored

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Air conditioning
Team: Facilities & Maintenance
Due by: 18 Oct, 7:49 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: 4th floor near pantry
- Issue: AC not cooling


Regards,
Workplace Team
```

#### test_laptop_issue_blocked_then_done_by_it — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "laptop". They wrote: "my laptop is not booting, shows blue screen"
2. it.servicess8989@gmail.com sent an email. Subject: "Re: Work Order: Laptop not booting (blue screen) [ITS-2026-0001]". They wrote: "need the motherboard from dell, 3 days"
3. it.servicess8989@gmail.com sent an email. Subject: "Re: Work Order: Laptop not booting (blue screen) [ITS-2026-0001]". They wrote: "replaced the board, laptop returned to user"
4. The desk opened ITS-2026-0001 (Laptop not booting (blue screen)) — closed as done.
5. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 3 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
6. It wrote to it.servicess8989@gmail.com. Subject: "Work Order: Laptop not booting (blue screen) [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Laptop not booting (blue screen) Repair. No …"
7. It wrote to rohan.mehta@acme.demo. Subject: "Re: laptop [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, We have logged your request and assigned it to IT Support. Request: ITS-2026-0001 Subject: Laptop not booting (blue screen) Status: Open You …"
8. It wrote to skcbsa1221@gmail.com. Subject: "At Risk: Laptop not booting (blue screen) [ITS-2026-0001]". The message starts: "Dear Team, The following request is at risk of missing its due time. Request: ITS-2026-0001 Subject: Laptop not booting (blue screen) IT Support reports a prob…"
9. It wrote to rohan.mehta@acme.demo. Subject: "laptop [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, A quick update on ITS-2026-0001 (Laptop not booting (blue screen)): IT Support has hit a snag - Waiting for a motherboard from Dell (3 days) …"
10. It wrote to rohan.mehta@acme.demo. Subject: "laptop [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, Good news - ITS-2026-0001 (Laptop not booting (blue screen)) has been taken care of. Note from IT Support: Motherboard replaced, laptop retur…"
11. It wrote to skcbsa1221@gmail.com. Subject: "At Risk: Laptop not booting (blue screen) [ITS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ITS-2026-0001 Subject: Laptop not booting (blue screen) Completed by IT Support: Motherboard replaced, la…"
12. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Laptop not booting (blue screen) (RESOLVED, MEDIUM, stage RESOLVED, decision REPAIR_UNKNOWN)

Email received:

- From: rohan.mehta@acme.demo
- Subject: laptop

```
my laptop is not booting, shows blue screen
```

- From: it.servicess8989@gmail.com
- Subject: Re: Work Order: Laptop not booting (blue screen) [ITS-2026-0001]

```
need the motherboard from dell, 3 days
```

- From: it.servicess8989@gmail.com
- Subject: Re: Work Order: Laptop not booting (blue screen) [ITS-2026-0001]

```
replaced the board, laptop returned to user
```

Reply sent:

- To: it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Laptop not booting (blue screen) [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Laptop not booting (blue screen)

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Laptop / device
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Issue: laptop not booting, blue screen

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> …
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: laptop [ITS-2026-0001]

```
Dear Rohan Mehta,

We have logged your request and assigned it to IT Support.

Request: ITS-2026-0001
Subject: Laptop not booting (blue screen)
Status: Open

You will be updated on this thread when the work is complete.
No asset record matched this request at your branch, so warranty and repair history were not applied.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: At Risk: Laptop not booting (blue screen) [ITS-2026-0001]

```
Dear Team,

The following request is at risk of missing its due time.

Request: ITS-2026-0001
Subject: Laptop not booting (blue screen)

IT Support reports a problem: Waiting for a motherboard from Dell (3 days)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Laptop / device
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Issue: laptop not booting, blue screen

Please reply "assign to <email>" to transfer it, "tell requester: <message>" to update the requester, "done - <note>" if it is already complete, or "cancel".

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: laptop [ITS-2026-0001]

```
Dear Rohan Mehta,

A quick update on ITS-2026-0001 (Laptop not booting (blue screen)): IT Support has hit a snag - Waiting for a motherboard from Dell (3 days)

We're on it and will update you as soon as it moves.

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: laptop [ITS-2026-0001]

```
Dear Rohan Mehta,

Good news - ITS-2026-0001 (Laptop not booting (blue screen)) has been taken care of.
Note from IT Support: Motherboard replaced, laptop returned

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: At Risk: Laptop not booting (blue screen) [ITS-2026-0001]

```
Dear Team,

Please note the following update.

Request: ITS-2026-0001
Subject: Laptop not booting (blue screen)

Completed by IT Support: Motherboard replaced, laptop returned

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Laptop / device
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Issue: laptop not booting, blue screen


Regards,
Workplace Team
```

#### test_catering_needs_approval_cafeteria_head_approves — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "lunch". They wrote: "Need lunch for 20 people tomorrow 1 PM in the board room"
2. cateringservices4656@gmail.com sent an email. Subject: "Re: Ops Decision: Lunch for 20, tomorrow 1 PM [CAT-2026-0001]". They wrote: "approve"
3. cateringservices4656@gmail.com sent an email. Subject: "Re: Work Order: Lunch for 20, tomorrow 1 PM [CAT-2026-0001]". They wrote: "lunch served"
4. The desk opened CAT-2026-0001 (Lunch for 20, tomorrow 1 PM) — closed as done.
5. It checked the records. Nothing in the records blocked it, so the desk carried on.
6. It wrote to skcbsa1221@gmail.com, cateringservices4656@gmail.com. Subject: "Ops Decision: Lunch for 20, tomorrow 1 PM [CAT-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: CAT-2026-0001 Subject: Lunch for 20, tomorrow 1 PM Needs your approval - catering is…"
7. It wrote to rohan.mehta@acme.demo. Subject: "Re: lunch [CAT-2026-0001]". The message starts: "Dear Rohan Mehta, Your request has been logged and sent for approval. Request: CAT-2026-0001 Subject: Lunch for 20, tomorrow 1 PM You will be updated on this t…"
8. It wrote to cateringservices4656@gmail.com. Subject: "Work Order: Lunch for 20, tomorrow 1 PM [CAT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: CAT-2026-0001 Subject: Lunch for 20, tomorrow 1 PM New work order R…"
9. It wrote to rohan.mehta@acme.demo. Subject: "lunch [CAT-2026-0001]". The message starts: "Dear Rohan Mehta, Request CAT-2026-0001 (Lunch for 20, tomorrow 1 PM) is approved and assigned to Cafeteria & Catering. You will be updated on this thread when…"
10. It wrote to rohan.mehta@acme.demo. Subject: "lunch [CAT-2026-0001]". The message starts: "Dear Rohan Mehta, Good news - CAT-2026-0001 (Lunch for 20, tomorrow 1 PM) has been taken care of. Note from Cafeteria & Catering: Lunch for 20 served in the bo…"
11. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: Lunch for 20, tomorrow 1 PM [CAT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: CAT-2026-0001 Subject: Lunch for 20, tomorrow 1 PM Completed by Cafeteria & Catering: Lunch for 20 served…"
12. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- CAT-2026-0001: Lunch for 20, tomorrow 1 PM (RESOLVED, MEDIUM, stage RESOLVED, decision PROCEED)

Email received:

- From: rohan.mehta@acme.demo
- Subject: lunch

```
Need lunch for 20 people tomorrow 1 PM in the board room
```

- From: cateringservices4656@gmail.com
- Subject: Re: Ops Decision: Lunch for 20, tomorrow 1 PM [CAT-2026-0001]

```
approve
```

- From: cateringservices4656@gmail.com
- Subject: Re: Work Order: Lunch for 20, tomorrow 1 PM [CAT-2026-0001]

```
lunch served
```

Reply sent:

- To: skcbsa1221@gmail.com, cateringservices4656@gmail.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Lunch for 20, tomorrow 1 PM [CAT-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: CAT-2026-0001
Subject: Lunch for 20, tomorrow 1 PM

Needs your approval - catering is chargeable - cost sign-off needed before ordering

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Catering
Team: Cafeteria & Catering
Preferred vendor: FreshServe Catering Pvt. Ltd. <orders@freshserve.demo>

Details:
- Date: tomorrow
- Time: 1 PM
- Headcount: 20
- Location: board room

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: lunch [CAT-2026-0001]

```
Dear Rohan Mehta,

Your request has been logged and sent for approval.

Request: CAT-2026-0001
Subject: Lunch for 20, tomorrow 1 PM

You will be updated on this thread once a decision is recorded.

Regards,
Workplace Team
```

- To: cateringservices4656@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Lunch for 20, tomorrow 1 PM [CAT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: CAT-2026-0001
Subject: Lunch for 20, tomorrow 1 PM

New work order

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Catering
Team: Cafeteria & Catering
Due by: 18 Oct, 11:49 AM
Preferred vendor: FreshServe Catering Pvt. Ltd. <orders@freshserve.demo>

Details:
- Date: tomorrow
- Time: 1 PM
- Headcount: 20
- Location: board room

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was served and the headcount>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or priority is wro…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: lunch [CAT-2026-0001]

```
Dear Rohan Mehta,

Request CAT-2026-0001 (Lunch for 20, tomorrow 1 PM) is approved and assigned to Cafeteria & Catering. You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: lunch [CAT-2026-0001]

```
Dear Rohan Mehta,

Good news - CAT-2026-0001 (Lunch for 20, tomorrow 1 PM) has been taken care of.
Note from Cafeteria & Catering: Lunch for 20 served in the board room

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Lunch for 20, tomorrow 1 PM [CAT-2026-0001]

```
Dear Team,

Please note the following update.

Request: CAT-2026-0001
Subject: Lunch for 20, tomorrow 1 PM

Completed by Cafeteria & Catering: Lunch for 20 served in the board room

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Catering
Team: Cafeteria & Catering
Due by: 18 Oct, 11:49 AM
Preferred vendor: FreshServe Catering Pvt. Ltd. <orders@freshserve.demo>

Details:
- Date: tomorrow
- Time: 1 PM
- Headcount: 20
- Location: board room


Regards,
Workplace Team
```

#### test_catering_date_given_later_waits_for_approval_and_is_due_by_the_meal — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "need catering". They wrote: "i need food for 30 people , on 3rd floor , 10 veg rest non veg"
2. rohan.mehta@acme.demo sent an email. Subject: "Re: need catering". They wrote: "18 October 2026, 02:49"
3. skcbsa1221@gmail.com sent an email. Subject: "Re: Ops Decision: Catering for 30 people on 3rd floor [CAT-2026-0001]". They wrote: "approve"
4. The desk opened CAT-2026-0001 (Catering for 30 people on 3rd floor) — handed to the team and still open.
5. It checked the records. Nothing in the records blocked it, so the desk carried on.
6. It wrote to rohan.mehta@acme.demo. Subject: "Re: need catering [CAT-2026-0001]". The message starts: "Dear Rohan Mehta, Your request has been logged. Request: CAT-2026-0001 Subject: Catering for 30 people on 3rd floor Please reply with the following: - For whic…"
7. It wrote to skcbsa1221@gmail.com, cateringservices4656@gmail.com. Subject: "Ops Decision: Catering for 30 people on 3rd floor [CAT-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: CAT-2026-0001 Subject: Catering for 30 people on 3rd floor Needs your approval - cat…"
8. It wrote to rohan.mehta@acme.demo. Subject: "Re: need catering [CAT-2026-0001]". The message starts: "Dear Rohan Mehta, Your request has been logged and sent for approval. Request: CAT-2026-0001 Subject: Catering for 30 people on 3rd floor You will be updated o…"
9. It wrote to cateringservices4656@gmail.com. Subject: "Work Order: Catering for 30 people on 3rd floor [CAT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: CAT-2026-0001 Subject: Catering for 30 people on 3rd floor New work…"
10. It wrote to rohan.mehta@acme.demo. Subject: "need catering [CAT-2026-0001]". The message starts: "Dear Rohan Mehta, Request CAT-2026-0001 (Catering for 30 people on 3rd floor) is approved and assigned to Cafeteria & Catering. You will be updated on this thr…"
11. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- CAT-2026-0001: Catering for 30 people on 3rd floor (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: rohan.mehta@acme.demo
- Subject: need catering

```
i need food for 30 people , on 3rd floor , 10 veg rest non veg
```

- From: rohan.mehta@acme.demo
- Subject: Re: need catering

```
18 October 2026, 02:49
```

- From: skcbsa1221@gmail.com
- Subject: Re: Ops Decision: Catering for 30 people on 3rd floor [CAT-2026-0001]

```
approve
```

Reply sent:

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: need catering [CAT-2026-0001]

```
Dear Rohan Mehta,

Your request has been logged.

Request: CAT-2026-0001
Subject: Catering for 30 people on 3rd floor

Please reply with the following:
- For which date and time?
- For which date?
- What time should it be ready?

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com, cateringservices4656@gmail.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Catering for 30 people on 3rd floor [CAT-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: CAT-2026-0001
Subject: Catering for 30 people on 3rd floor

Needs your approval - catering is chargeable - cost sign-off needed before ordering

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Catering
Team: Cafeteria & Catering
Preferred vendor: FreshServe Catering Pvt. Ltd. <orders@freshserve.demo>

Details:
- Headcount: 30
- Location: 3rd floor
- Meal preference: 10 veg, 20 non-veg
- Date: 18 October 2026
- Time: 02:49

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: need catering [CAT-2026-0001]

```
Dear Rohan Mehta,

Your request has been logged and sent for approval.

Request: CAT-2026-0001
Subject: Catering for 30 people on 3rd floor

You will be updated on this thread once a decision is recorded.

Regards,
Workplace Team
```

- To: cateringservices4656@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Catering for 30 people on 3rd floor [CAT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: CAT-2026-0001
Subject: Catering for 30 people on 3rd floor

New work order

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Catering
Team: Cafeteria & Catering
Due by: 18 Oct, 2:49 AM
Preferred vendor: FreshServe Catering Pvt. Ltd. <orders@freshserve.demo>

Details:
- Headcount: 30
- Location: 3rd floor
- Meal preference: 10 veg, 20 non-veg
- Date: 18 October 2026
- Time: 02:49

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was served and the headcount>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached …
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: need catering [CAT-2026-0001]

```
Dear Rohan Mehta,

Request CAT-2026-0001 (Catering for 30 people on 3rd floor) is approved and assigned to Cafeteria & Catering. You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

#### test_one_mail_many_cases_keeps_the_name_and_says_which_case — PASSED

What happened:

1. kmantri1204@gmail.com sent an email. Subject: "Re: stationery request". They wrote: "I am new joiner, need assistance in access card and seating"
2. skcbsa1221@gmail.com sent an email. Subject: "Re: Ops Decision: Access card and ID issuance [ITS-2026-0001]". They wrote: "Approve"
3. The desk opened ITS-2026-0001 (Access card and ID issuance) — handed to the team and still open; SEAT-2026-0001 (Desk allocation and seating) — completed.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 3 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
5. It wrote to skcbsa1221@gmail.com, it.servicess8989@gmail.com. Subject: "Ops Decision: Access card and ID issuance [ITS-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: ITS-2026-0001 Subject: Access card and ID issuance Needs your approval - flagged as …"
6. It wrote to skcbsa1221@gmail.com. Subject: "Done: Desk allocation and seating [SEAT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: SEAT-2026-0001 Subject: Desk allocation and seating Seat allotted: Seat-16 Requester: Kapil Mantri <kmant…"
7. It wrote to kmantri1204@gmail.com. Subject: "Re: stationery request [ITS-2026-0001] [SEAT-2026-0001]". The message starts: "Dear Kapil Mantri, Your request has been logged and sent for approval. Request: ITS-2026-0001 Subject: Access card and ID issuance You will be updated on this …"
8. It wrote to it.servicess8989@gmail.com. Subject: "Work Order: Access card and ID issuance [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Access card and ID issuance Repair. No asset…"
9. It wrote to kmantri1204@gmail.com. Subject: "Access card and ID issuance [ITS-2026-0001]". The message starts: "Dear Kapil Mantri, Request ITS-2026-0001 (Access card and ID issuance) is approved and assigned to IT Support. You will be updated on this thread when the work…"
10. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Access card and ID issuance (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR_UNKNOWN)
- SEAT-2026-0001: Desk allocation and seating (ACTIVE, MEDIUM, stage COMPLETED, decision PROCEED)

Email received:

- From: kmantri1204@gmail.com
- Subject: Re: stationery request

```
I am new joiner, need assistance in access card and seating
```

- From: skcbsa1221@gmail.com
- Subject: Re: Ops Decision: Access card and ID issuance [ITS-2026-0001]

```
Approve
```

Reply sent:

- To: skcbsa1221@gmail.com, it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Access card and ID issuance [ITS-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: ITS-2026-0001
Subject: Access card and ID issuance

Needs your approval - flagged as sensitive

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Kapil Mantri <kmantri1204@gmail.com>
Type: Access card / ID
Team: IT Support

Details:
- Employee name: Kapil Mantri

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Done: Desk allocation and seating [SEAT-2026-0001]

```
Dear Team,

Please note the following update.

Request: SEAT-2026-0001
Subject: Desk allocation and seating

Seat allotted: Seat-16

Requester: Kapil Mantri <kmantri1204@gmail.com>
Type: Seating / desk move
Team: Admin & Workplace
Due by: 18 Oct, 11:49 PM

Details:
- Employee name: Kapil Mantri
- Start date: 5 Oct
- Date: 5 Oct


Regards,
Workplace Team
```

- To: kmantri1204@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: stationery request [ITS-2026-0001] [SEAT-2026-0001]

```
Dear Kapil Mantri,

Your request has been logged and sent for approval.

Request: ITS-2026-0001
Subject: Access card and ID issuance

You will be updated on this thread once a decision is recorded.

Parking has been arranged.

Request: SEAT-2026-0001

Regards,
Workplace Team
```

- To: it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Access card and ID issuance [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Access card and ID issuance

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Kapil Mantri <kmantri1204@gmail.com>
Type: Access card / ID
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Employee name: Kapil Mantri

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <the card number issued or access granted>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "ca…
```

- To: kmantri1204@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Access card and ID issuance [ITS-2026-0001]

```
Dear Kapil Mantri,

Request ITS-2026-0001 (Access card and ID issuance) is approved and assigned to IT Support. You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

#### test_flight_and_taxi_details_later_keep_case_numbers_and_right_vendor — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "Travel arrangement". They wrote: "Pls book the flight ticket for me, I need taxi booking also"
2. rohan.mehta@acme.demo sent an email. Subject: "Re: Travel arrangement". They wrote: "morning flight Delhi to Pune on 10th Oct, 8 to 10.30 am. Sedan taxi at Pune airport for the whole day"
3. skcbsa1221@gmail.com sent an email. Subject: "Re: Ops Decision: Book flight ticket [TRV-2026-0001]". They wrote: "approve"
4. skcbsa1221@gmail.com sent an email. Subject: "Re: Work Order: Book taxi / cab [TRV-2026-0002]". They wrote: "the flight ticket is booked as well, tickets will be shared to him within 2 days"
5. The desk opened TRV-2026-0001 (Book flight ticket) — closed as done; TRV-2026-0002 (Book taxi / cab) — handed to the team and still open.
6. It checked the records. Nothing in the records blocked it, so the desk carried on.
7. It wrote to rohan.mehta@acme.demo. Subject: "Re: Travel arrangement [TRV-2026-0001] [TRV-2026-0002]". The message starts: "Dear Rohan Mehta, Your request has been logged. Request: TRV-2026-0001 Subject: Book flight ticket Please reply with the following: - When do you need to trave…"
8. It wrote to skcbsa1221@gmail.com. Subject: "Ops Decision: Book flight ticket [TRV-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: TRV-2026-0001 Subject: Book flight ticket Needs your approval - flight / train / hot…"
9. It wrote to skcbsa1221@gmail.com. Subject: "Work Order: Book taxi / cab [TRV-2026-0002]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TRV-2026-0002 Subject: Book taxi / cab New work order (No Travel De…"
10. It wrote to rohan.mehta@acme.demo. Subject: "Re: Travel arrangement [TRV-2026-0001] [TRV-2026-0002]". The message starts: "Hi, I have noted the details for your flight TRV-2026-0001 and taxi booking TRV-2026-0002. The flight needs approval first; I'll update you here. Possible flig…"
11. It wrote to skcbsa1221@gmail.com. Subject: "Ops Decision: Book flight ticket [TRV-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TRV-2026-0001 Subject: Book flight ticket New work order (No Travel…"
12. It wrote to rohan.mehta@acme.demo. Subject: "Book flight ticket [TRV-2026-0001]". The message starts: "Dear Rohan Mehta, Request TRV-2026-0001 (Book flight ticket) is approved and assigned to Travel Desk. You will be updated on this thread when the work is compl…"
13. It wrote to rohan.mehta@acme.demo. Subject: "Book flight ticket [TRV-2026-0001]". The message starts: "Dear Rohan Mehta, Good news - TRV-2026-0001 (Book flight ticket) has been taken care of. Note from Travel Desk: Your flight ticket is booked; the tickets will …"
14. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TRV-2026-0001: Book flight ticket (RESOLVED, MEDIUM, stage RESOLVED, decision PROCEED)
- TRV-2026-0002: Book taxi / cab (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: rohan.mehta@acme.demo
- Subject: Travel arrangement

```
Pls book the flight ticket for me, I need taxi booking also
```

- From: rohan.mehta@acme.demo
- Subject: Re: Travel arrangement

```
morning flight Delhi to Pune on 10th Oct, 8 to 10.30 am. Sedan taxi at Pune airport for the whole day
```

- From: skcbsa1221@gmail.com
- Subject: Re: Ops Decision: Book flight ticket [TRV-2026-0001]

```
approve
```

- From: skcbsa1221@gmail.com
- Subject: Re: Work Order: Book taxi / cab [TRV-2026-0002]

```
the flight ticket is booked as well, tickets will be shared to him within 2 days
```

Reply sent:

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Travel arrangement [TRV-2026-0001] [TRV-2026-0002]

```
Dear Rohan Mehta,

Your request has been logged.

Request: TRV-2026-0001
Subject: Book flight ticket

Please reply with the following:
- When do you need to travel (date and time)?
- From where to where?

Your request has been logged.

Request: TRV-2026-0002
Subject: Book taxi / cab

Please reply with the following:
- When do you need to travel (date and time)?
- From where to where?

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Book flight ticket [TRV-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: TRV-2026-0001
Subject: Book flight ticket

Needs your approval - flight / train / hotel bookings need approval before booking

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Travel / cab
Team: Travel Desk

Details:
- Travel date: 10 October 2026
- Pickup: Delhi
- Drop: Pune
- Timing: 8:00 AM to 10:30 AM flight
- Time: 8:00 AM

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Book taxi / cab [TRV-2026-0002]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TRV-2026-0002
Subject: Book taxi / cab

New work order
(No Travel Desk contact set yet - sent to you. Add it in Company setup.)

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Travel / cab
Team: Travel Desk
Due by: 18 Oct, 11:49 AM

Details:
- Travel date: 10 October 2026
- Pickup: Pune airport
- Drop: Pune airport
- Vehicle type: sedan
- Time: morning

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <the booking reference / cab and driver details>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your repl…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Travel arrangement [TRV-2026-0001] [TRV-2026-0002]

```
Hi,

I have noted the details for your flight TRV-2026-0001 and taxi booking TRV-2026-0002. The flight needs approval first; I'll update you here.

Possible flight timings (schedule only — fares are confirmed by Travel Desk, not auto-quoted):

Travel Desk has the request and will send exact airline / time / fare options on this thread.
Reply with the option number (or preferred time window). I'll ask Travel Desk to lock it after approval if required.

Possible flight timings (schedule only — fares are confirmed by Travel Desk, not auto-quoted):

Travel Desk has the request and will send exact airline / time / fare options on this thread.
Reply with the option number (or preferred time window). I'll ask Travel Desk to lock it after approval if required.

Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Book flight ticket [TRV-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TRV-2026-0001
Subject: Book flight ticket

New work order
(No Travel Desk contact set yet - sent to you. Add it in Company setup.)

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Travel / cab
Team: Travel Desk
Due by: 18 Oct, 11:49 AM

Details:
- Travel date: 10 October 2026
- Pickup: Delhi
- Drop: Pune
- Timing: 8:00 AM to 10:30 AM flight
- Time: 8:00 AM

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <the booking reference / cab and driver details>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your r…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Book flight ticket [TRV-2026-0001]

```
Dear Rohan Mehta,

Request TRV-2026-0001 (Book flight ticket) is approved and assigned to Travel Desk. You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Book flight ticket [TRV-2026-0001]

```
Dear Rohan Mehta,

Good news - TRV-2026-0001 (Book flight ticket) has been taken care of.
Note from Travel Desk: Your flight ticket is booked; the tickets will be shared with you within 2 days.

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

#### test_sibling_cases_get_separate_team_threads_and_one_reply_can_close_both — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "Travel". They wrote: "book a flight Delhi to Pune on 10 Oct 8 am and a sedan taxi at Pune airport that day"
2. skcbsa1221@gmail.com sent an email. Subject: "Re: Ops Decision: Book flight ticket [TRV-2026-0001]". They wrote: "approve"
3. skcbsa1221@gmail.com sent an email. Subject: "Re: Ops Decision: Book flight ticket [TRV-2026-0001]". They wrote: "cab and flight both booked, details on the day"
4. The desk opened TRV-2026-0001 (Book flight ticket) — closed as done; TRV-2026-0002 (Book taxi / cab) — closed as done.
5. It checked the records. Nothing in the records blocked it, so the desk carried on.
6. It wrote to skcbsa1221@gmail.com. Subject: "Ops Decision: Book flight ticket [TRV-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: TRV-2026-0001 Subject: Book flight ticket Needs your approval - flight / train / hot…"
7. It wrote to skcbsa1221@gmail.com. Subject: "Work Order: Book taxi / cab [TRV-2026-0002]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TRV-2026-0002 Subject: Book taxi / cab New work order (No Travel De…"
8. It wrote to rohan.mehta@acme.demo. Subject: "Re: Travel [TRV-2026-0001] [TRV-2026-0002]". The message starts: "Dear Rohan Mehta, Your request has been logged and sent for approval. Request: TRV-2026-0001 Subject: Book flight ticket You will be updated on this thread onc…"
9. It wrote to skcbsa1221@gmail.com. Subject: "Ops Decision: Book flight ticket [TRV-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TRV-2026-0001 Subject: Book flight ticket New work order (No Travel…"
10. It wrote to rohan.mehta@acme.demo. Subject: "Book flight ticket [TRV-2026-0001]". The message starts: "Dear Rohan Mehta, Request TRV-2026-0001 (Book flight ticket) is approved and assigned to Travel Desk. You will be updated on this thread when the work is compl…"
11. It wrote to rohan.mehta@acme.demo. Subject: "Book flight ticket [TRV-2026-0001]". The message starts: "Dear Rohan Mehta, Good news - TRV-2026-0001 (Book flight ticket) has been taken care of. Note from Travel Desk: Your cab and flight are both booked; details wi…"
12. It wrote to rohan.mehta@acme.demo. Subject: "Book taxi / cab [TRV-2026-0002]". The message starts: "Dear Rohan Mehta, Good news - TRV-2026-0002 (Book taxi / cab) has been taken care of. Note from Travel Desk: Your cab and flight are both booked; details will …"
13. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TRV-2026-0001: Book flight ticket (RESOLVED, MEDIUM, stage RESOLVED, decision PROCEED)
- TRV-2026-0002: Book taxi / cab (RESOLVED, MEDIUM, stage RESOLVED, decision PROCEED)

Email received:

- From: rohan.mehta@acme.demo
- Subject: Travel

```
book a flight Delhi to Pune on 10 Oct 8 am and a sedan taxi at Pune airport that day
```

- From: skcbsa1221@gmail.com
- Subject: Re: Ops Decision: Book flight ticket [TRV-2026-0001]

```
approve
```

- From: skcbsa1221@gmail.com
- Subject: Re: Ops Decision: Book flight ticket [TRV-2026-0001]

```
cab and flight both booked, details on the day
```

Reply sent:

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Book flight ticket [TRV-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: TRV-2026-0001
Subject: Book flight ticket

Needs your approval - flight / train / hotel bookings need approval before booking

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Travel / cab
Team: Travel Desk

Details:
- Travel date: 10 October 2026
- Pickup: Delhi
- Drop: Pune
- Time: 8 am

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Book taxi / cab [TRV-2026-0002]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TRV-2026-0002
Subject: Book taxi / cab

New work order
(No Travel Desk contact set yet - sent to you. Add it in Company setup.)

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Travel / cab
Team: Travel Desk
Due by: 18 Oct, 11:49 AM

Details:
- Travel date: 10 October 2026
- Pickup: Pune airport
- Drop: Pune airport
- Time: 8 am

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <the booking reference / cab and driver details>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or …
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Travel [TRV-2026-0001] [TRV-2026-0002]

```
Dear Rohan Mehta,

Your request has been logged and sent for approval.

Request: TRV-2026-0001
Subject: Book flight ticket

You will be updated on this thread once a decision is recorded.

We have logged your request and assigned it to Travel Desk.

Request: TRV-2026-0002
Subject: Book taxi / cab
Status: Open

You will be updated on this thread when the work is complete.

Possible flight timings (schedule only — fares are confirmed by Travel Desk, not auto-quoted):

Travel Desk has the request and will send exact airline / time / fare options on this thread.
Reply with the option number (or preferred time window). I'll ask Travel Desk to lock it after approval if required.

Possible flight timings (schedule only — fares are confirmed by Travel Desk, not auto-quoted):

Travel Desk has the request and will send exact airline / time / fare options on this thread.
Reply with the option numb…
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Ops Decision: Book flight ticket [TRV-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TRV-2026-0001
Subject: Book flight ticket

New work order
(No Travel Desk contact set yet - sent to you. Add it in Company setup.)

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Travel / cab
Team: Travel Desk
Due by: 18 Oct, 11:49 AM

Details:
- Travel date: 10 October 2026
- Pickup: Delhi
- Drop: Pune
- Time: 8 am

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <the booking reference / cab and driver details>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or priority is …
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Book flight ticket [TRV-2026-0001]

```
Dear Rohan Mehta,

Request TRV-2026-0001 (Book flight ticket) is approved and assigned to Travel Desk. You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Book flight ticket [TRV-2026-0001]

```
Dear Rohan Mehta,

Good news - TRV-2026-0001 (Book flight ticket) has been taken care of.
Note from Travel Desk: Your cab and flight are both booked; details will follow on the day.

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Book taxi / cab [TRV-2026-0002]

```
Dear Rohan Mehta,

Good news - TRV-2026-0002 (Book taxi / cab) has been taken care of.
Note from Travel Desk: Your cab and flight are both booked; details will follow on the day.

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

#### test_team_note_after_close_does_not_reopen_or_send_good_news — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "charger". They wrote: "my laptop charger stopped working, need a new one"
2. skcbsa1221@gmail.com sent an email. Subject: "Re: Work Order: Laptop charger replacement [ITS-2026-0001]". They wrote: "close this"
3. skcbsa1221@gmail.com sent an email. Subject: "Re: Work Order: Laptop charger replacement [ITS-2026-0001]". They wrote: "it was delivered on time"
4. The desk opened ITS-2026-0001 (Laptop charger replacement) — closed.
5. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 3 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
6. It wrote to it.servicess8989@gmail.com. Subject: "Work Order: Laptop charger replacement [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Laptop charger replacement Repair. No asset …"
7. It wrote to rohan.mehta@acme.demo. Subject: "Re: charger [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, We have logged your request and assigned it to IT Support. Request: ITS-2026-0001 Subject: Laptop charger replacement Status: Open You will b…"
8. It wrote to rohan.mehta@acme.demo. Subject: "charger [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, ITS-2026-0001 (Laptop charger replacement) is now closed. Reply here if you need anything else. Regards, Workplace Team"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Laptop charger replacement (CLOSED, MEDIUM, stage CLOSED, decision REPAIR_UNKNOWN)

Email received:

- From: rohan.mehta@acme.demo
- Subject: charger

```
my laptop charger stopped working, need a new one
```

- From: skcbsa1221@gmail.com
- Subject: Re: Work Order: Laptop charger replacement [ITS-2026-0001]

```
close this
```

- From: skcbsa1221@gmail.com
- Subject: Re: Work Order: Laptop charger replacement [ITS-2026-0001]

```
it was delivered on time
```

Reply sent:

- To: it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Laptop charger replacement [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Laptop charger replacement

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Laptop / device
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Item: laptop charger

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: charger [ITS-2026-0001]

```
Dear Rohan Mehta,

We have logged your request and assigned it to IT Support.

Request: ITS-2026-0001
Subject: Laptop charger replacement
Status: Open

You will be updated on this thread when the work is complete.
No asset record matched this request at your branch, so warranty and repair history were not applied.

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: charger [ITS-2026-0001]

```
Dear Rohan Mehta,

ITS-2026-0001 (Laptop charger replacement) is now closed. Reply here if you need anything else.

Regards,
Workplace Team
```

#### test_pickup_message_after_resolution_reaches_the_requester — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "charger". They wrote: "my laptop charger stopped working, need a new one"
2. it.servicess8989@gmail.com sent an email. Subject: "Re: Work Order: Laptop charger replacement [ITS-2026-0001]". They wrote: "charger replaced"
3. it.servicess8989@gmail.com sent an email. Subject: "Re: Work Order: Laptop charger replacement [ITS-2026-0001]". They wrote: "all set, he can pick it up from the helpdesk on second floor"
4. The desk opened ITS-2026-0001 (Laptop charger replacement) — closed as done.
5. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 3 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
6. It wrote to it.servicess8989@gmail.com. Subject: "Work Order: Laptop charger replacement [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Laptop charger replacement Repair. No asset …"
7. It wrote to rohan.mehta@acme.demo. Subject: "Re: charger [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, We have logged your request and assigned it to IT Support. Request: ITS-2026-0001 Subject: Laptop charger replacement Status: Open You will b…"
8. It wrote to rohan.mehta@acme.demo. Subject: "charger [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, Good news - ITS-2026-0001 (Laptop charger replacement) has been taken care of. Note from IT Support: Charger replaced If anything is still no…"
9. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: Laptop charger replacement [ITS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ITS-2026-0001 Subject: Laptop charger replacement Completed by IT Support: Charger replaced Record check:…"
10. It wrote to it.servicess8989@gmail.com. Subject: "Work Order: Laptop charger replacement [ITS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ITS-2026-0001 Subject: Laptop charger replacement Thanks for completing this. To close it as verified, pl…"
11. It wrote to rohan.mehta@acme.demo. Subject: "charger [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, Message about ITS-2026-0001 (Laptop charger replacement) from IT Support: Everything is set - you can pick it up from the helpdesk on the sec…"
12. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Laptop charger replacement (RESOLVED, MEDIUM, stage RESOLVED, decision REPAIR_UNKNOWN)

Email received:

- From: rohan.mehta@acme.demo
- Subject: charger

```
my laptop charger stopped working, need a new one
```

- From: it.servicess8989@gmail.com
- Subject: Re: Work Order: Laptop charger replacement [ITS-2026-0001]

```
charger replaced
```

- From: it.servicess8989@gmail.com
- Subject: Re: Work Order: Laptop charger replacement [ITS-2026-0001]

```
all set, he can pick it up from the helpdesk on second floor
```

Reply sent:

- To: it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Laptop charger replacement [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Laptop charger replacement

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Laptop / device
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Item: laptop charger

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: charger [ITS-2026-0001]

```
Dear Rohan Mehta,

We have logged your request and assigned it to IT Support.

Request: ITS-2026-0001
Subject: Laptop charger replacement
Status: Open

You will be updated on this thread when the work is complete.
No asset record matched this request at your branch, so warranty and repair history were not applied.

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: charger [ITS-2026-0001]

```
Dear Rohan Mehta,

Good news - ITS-2026-0001 (Laptop charger replacement) has been taken care of.
Note from IT Support: Charger replaced

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Laptop charger replacement [ITS-2026-0001]

```
Dear Team,

Please note the following update.

Request: ITS-2026-0001
Subject: Laptop charger replacement

Completed by IT Support: Charger replaced

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Laptop / device
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Item: laptop charger


Regards,
Workplace Team
```

- To: it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Laptop charger replacement [ITS-2026-0001]

```
Dear Team,

Please note the following update.

Request: ITS-2026-0001
Subject: Laptop charger replacement

Thanks for completing this. To close it as verified, please reply with what was done and the asset tag / ticket number if any (or attach a photo).

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Laptop / device
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Item: laptop charger


Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: charger [ITS-2026-0001]

```
Dear Rohan Mehta,

Message about ITS-2026-0001 (Laptop charger replacement) from IT Support: Everything is set - you can pick it up from the helpdesk on the second floor.

Regards,
Workplace Team
```

#### test_reference_goes_above_the_signature — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_overdue_alert_tells_the_admin_what_they_can_reply — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "AC". They wrote: "AC not cooling at 4th floor"
2. The desk opened TKT-2026-0001 (AC not cooling) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to flexxftw12@gmail.com. Subject: "Work Order: AC not cooling [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: AC not cooling Repair This item. Repairs on …"
5. It wrote to rohan.mehta@acme.demo. Subject: "Re: AC [TKT-2026-0001]". The message starts: "Dear Rohan Mehta, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
6. It wrote to skcbsa1221@gmail.com. Subject: "Escalation: AC not cooling [TKT-2026-0001]". The message starts: "Dear Team, The following request has been escalated and requires attention. Request: TKT-2026-0001 Subject: AC not cooling SLA missed - Facilities has not clos…"
7. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: AC not cooling (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: rohan.mehta@acme.demo
- Subject: AC

```
AC not cooling at 4th floor
```

Reply sent:

- To: flexxftw12@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: AC not cooling [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: AC not cooling

Repair This item. Repairs on record: 0 of 6.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Air conditioning
Team: Facilities & Maintenance
Due by: 18 Oct, 7:49 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: 4th floor

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <email>" to transfer the work order
- "tell requ…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: AC [TKT-2026-0001]

```
Dear Rohan Mehta,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Escalation: AC not cooling [TKT-2026-0001]

```
Dear Team,

The following request has been escalated and requires attention.

Request: TKT-2026-0001
Subject: AC not cooling

SLA missed - Facilities has not closed this

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Air conditioning
Team: Facilities & Maintenance
Due by: 18 Oct, 7:49 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: 4th floor

Please reply "assign to <email>" to transfer it, "tell requester: <message>" to update the requester, "done - <note>" if it is already complete, or "cancel".

Regards,
Workplace Team
```

#### test_visitor_with_no_security_inbox_goes_to_admin — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "visitor". They wrote: "Visitor Neha Kapoor from Deloitte on 8 Oct 3 PM"
2. The desk opened VIS-2026-0001 (Visitor Neha Kapoor) — completed.
3. It checked the records. Nothing in the records blocked it, so the desk carried on.
4. It wrote to skcbsa1221@gmail.com. Subject: "Done: Visitor Neha Kapoor [VIS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: VIS-2026-0001 Subject: Visitor Neha Kapoor Visitor pre-registered - add to today's gate manifest (No Secu…"
5. It wrote to rohan.mehta@acme.demo. Subject: "Re: visitor [VIS-2026-0001]". The message starts: "Dear Rohan Mehta, Your visitors have been pre-registered. Request: VIS-2026-0001 - Neha Kapoor: pass VP-BA08F4 Please ask each visitor to carry a photo identit…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- VIS-2026-0001: Visitor Neha Kapoor (ACTIVE, MEDIUM, stage COMPLETED, decision PROCEED)

Email received:

- From: rohan.mehta@acme.demo
- Subject: visitor

```
Visitor Neha Kapoor from Deloitte on 8 Oct 3 PM
```

Reply sent:

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Done: Visitor Neha Kapoor [VIS-2026-0001]

```
Dear Team,

Please note the following update.

Request: VIS-2026-0001
Subject: Visitor Neha Kapoor

Visitor pre-registered - add to today's gate manifest
(No Security & Front Desk contact set yet - sent to you. Add it in Company setup.)

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Visitor pre-registration
Team: Security & Front Desk
Due by: 18 Oct, 3:49 AM

Details:
- Visitor names: Neha Kapoor (Deloitte)
- Visit date: 8 Oct
- Time: 3 PM
- Pass VP-BA08F4: Neha Kapoor (Deloitte)


Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: visitor [VIS-2026-0001]

```
Dear Rohan Mehta,

Your visitors have been pre-registered.

Request: VIS-2026-0001
- Neha Kapoor: pass VP-BA08F4
Please ask each visitor to carry a photo identity card and meet you at reception.

Regards,
Workplace Team
```

#### test_admin_team_request_is_handled_by_the_admin_inbox — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "supplies". They wrote: "Need 10 notebooks and 10 pens for the training room"
2. skcbsa1221@gmail.com sent an email. Subject: "Re: Work Order: 10 notebooks and 10 pens [SUP-2026-0001]". They wrote: "kept in the training room"
3. The desk opened SUP-2026-0001 (10 notebooks and 10 pens) — closed as done.
4. It checked the records. Nothing in the records blocked it, so the desk carried on.
5. It wrote to skcbsa1221@gmail.com. Subject: "Work Order: 10 notebooks and 10 pens [SUP-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: SUP-2026-0001 Subject: 10 notebooks and 10 pens New work order Requ…"
6. It wrote to rohan.mehta@acme.demo. Subject: "Re: supplies [SUP-2026-0001]". The message starts: "Dear Rohan Mehta, We have logged your request and assigned it to Admin & Workplace. Request: SUP-2026-0001 Subject: 10 notebooks and 10 pens Status: Open You w…"
7. It wrote to rohan.mehta@acme.demo. Subject: "supplies [SUP-2026-0001]". The message starts: "Dear Rohan Mehta, Good news - SUP-2026-0001 (10 notebooks and 10 pens) has been taken care of. Note from Admin & Workplace: Notebooks and pens placed in the tr…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- SUP-2026-0001: 10 notebooks and 10 pens (RESOLVED, MEDIUM, stage RESOLVED, decision PROCEED)

Email received:

- From: rohan.mehta@acme.demo
- Subject: supplies

```
Need 10 notebooks and 10 pens for the training room
```

- From: skcbsa1221@gmail.com
- Subject: Re: Work Order: 10 notebooks and 10 pens [SUP-2026-0001]

```
kept in the training room
```

Reply sent:

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: 10 notebooks and 10 pens [SUP-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: SUP-2026-0001
Subject: 10 notebooks and 10 pens

New work order

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Office supplies
Team: Admin & Workplace
Due by: 18 Oct, 11:49 PM

Details:
- Items: 10 notebooks, 10 pens
- Location: training room

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was delivered and to whom>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
When the item is ready, state where and from whom to collect it (for example, "done - card ready, collect from IT desk, 3rd …
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: supplies [SUP-2026-0001]

```
Dear Rohan Mehta,

We have logged your request and assigned it to Admin & Workplace.

Request: SUP-2026-0001
Subject: 10 notebooks and 10 pens
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: supplies [SUP-2026-0001]

```
Dear Rohan Mehta,

Good news - SUP-2026-0001 (10 notebooks and 10 pens) has been taken care of.
Note from Admin & Workplace: Notebooks and pens placed in the training room

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

#### test_offboarding_needs_approval_then_only_it_gets_one_order — PASSED

What happened:

1. kshitiz.vishwakarma2003@gmail.com sent an email. Subject: "Exit - Rahul Verma". They wrote: "Rahul Verma's last working day is 10 Oct, please do exit formalities"
2. skcbsa1221@gmail.com sent an email. Subject: "Re: Ops Decision: Exit for Rahul Verma [EXT-2026-0001]". They wrote: "approve"
3. it.servicess8989@gmail.com sent an email. Subject: "Re: Work Order: Exit for Rahul Verma [EXT-2026-0001]". They wrote: "laptop collected and card deactivated"
4. The desk opened EXT-2026-0001 (Exit for Rahul Verma) — closed as done.
5. It checked the records. Nothing in the records blocked it, so the desk carried on.
6. It wrote to skcbsa1221@gmail.com, kshitiz.vishwakarma2003@gmail.com. Subject: "Ops Decision: Exit for Rahul Verma [EXT-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: EXT-2026-0001 Subject: Exit for Rahul Verma Needs your approval - offboarding reques…"
7. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "Re: Exit - Rahul Verma [EXT-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, Your request has been logged and sent for approval. Request: EXT-2026-0001 Subject: Exit for Rahul Verma You will be updated on this …"
8. It wrote to it.servicess8989@gmail.com. Subject: "Work Order: Exit for Rahul Verma [EXT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: EXT-2026-0001 Subject: Exit for Rahul Verma Employee exit - IT Supp…"
9. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "Exit - Rahul Verma [EXT-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, Request EXT-2026-0001 (Exit for Rahul Verma) is approved and assigned to IT Support. You will be updated on this thread when the work…"
10. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "Exit - Rahul Verma [EXT-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, Good news - EXT-2026-0001 (Exit for Rahul Verma) has been taken care of. Note from IT Support: Laptop collected, access card deactiva…"
11. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: Exit for Rahul Verma [EXT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: EXT-2026-0001 Subject: Exit for Rahul Verma Completed - IT Support finished the last part: Laptop collect…"
12. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- EXT-2026-0001: Exit for Rahul Verma (RESOLVED, MEDIUM, stage RESOLVED, decision PROCEED)

Email received:

- From: kshitiz.vishwakarma2003@gmail.com
- Subject: Exit - Rahul Verma

```
Rahul Verma's last working day is 10 Oct, please do exit formalities
```

- From: skcbsa1221@gmail.com
- Subject: Re: Ops Decision: Exit for Rahul Verma [EXT-2026-0001]

```
approve
```

- From: it.servicess8989@gmail.com
- Subject: Re: Work Order: Exit for Rahul Verma [EXT-2026-0001]

```
laptop collected and card deactivated
```

Reply sent:

- To: skcbsa1221@gmail.com, kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Exit for Rahul Verma [EXT-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: EXT-2026-0001
Subject: Exit for Rahul Verma

Needs your approval - offboarding requests need admin sign-off

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Employee exit
Team: People / HR

Details:
- Employee name: Rahul Verma
- Last working day: 10 Oct

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Exit - Rahul Verma [EXT-2026-0001]

```
Dear Kshitiz Vishwakarma,

Your request has been logged and sent for approval.

Request: EXT-2026-0001
Subject: Exit for Rahul Verma

You will be updated on this thread once a decision is recorded.

Regards,
Workplace Team
```

- To: it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Exit for Rahul Verma [EXT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: EXT-2026-0001
Subject: Exit for Rahul Verma

Employee exit - IT Support tasks

Tasks assigned:
1. Collect laptop and IT assets from Rahul Verma; disable email and system access after 10 Oct
2. Collect ID / access card from Rahul Verma and deactivate it after 10 Oct

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Employee exit
Teams working on it: IT Support
Due by: 18 Oct, 11:49 PM

Details:
- Employee name: Rahul Verma
- Last working day: 10 Oct

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done" when the work is complete, with a short note
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "clo…
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Exit - Rahul Verma [EXT-2026-0001]

```
Dear Kshitiz Vishwakarma,

Request EXT-2026-0001 (Exit for Rahul Verma) is approved and assigned to IT Support. You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Exit - Rahul Verma [EXT-2026-0001]

```
Dear Kshitiz Vishwakarma,

Good news - EXT-2026-0001 (Exit for Rahul Verma) has been taken care of.
Note from IT Support: Laptop collected, access card deactivated

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Exit for Rahul Verma [EXT-2026-0001]

```
Dear Team,

Please note the following update.

Request: EXT-2026-0001
Subject: Exit for Rahul Verma

Completed - IT Support finished the last part: Laptop collected, access card deactivated

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Employee exit
Teams working on it: IT Support
Due by: 18 Oct, 11:49 PM

Details:
- Employee name: Rahul Verma
- Last working day: 10 Oct


Regards,
Workplace Team
```

#### test_team_question_for_requester_is_passed_on — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "chair". They wrote: "Chair is broken at my desk 2F-08"
2. flexxftw12@gmail.com sent an email. Subject: "Re: Work Order: Broken chair at 2F-08 [TKT-2026-0001]". They wrote: "is it the armrest or the wheel? and when is the user at desk"
3. The desk opened TKT-2026-0001 (Broken chair at 2F-08) — handed to the team and still open.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 4 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
5. It wrote to flexxftw12@gmail.com. Subject: "Work Order: Broken chair at 2F-08 [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Broken chair at 2F-08 Repair. No asset recor…"
6. It wrote to rohan.mehta@acme.demo. Subject: "Re: chair [TKT-2026-0001]". The message starts: "Dear Rohan Mehta, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
7. It wrote to rohan.mehta@acme.demo. Subject: "chair [TKT-2026-0001]". The message starts: "Dear Rohan Mehta, Message about TKT-2026-0001 (Broken chair at 2F-08) from Facilities & Maintenance: Is it the armrest or the wheel, and when will you be at yo…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Broken chair at 2F-08 (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR_UNKNOWN)

Email received:

- From: rohan.mehta@acme.demo
- Subject: chair

```
Chair is broken at my desk 2F-08
```

- From: flexxftw12@gmail.com
- Subject: Re: Work Order: Broken chair at 2F-08 [TKT-2026-0001]

```
is it the armrest or the wheel? and when is the user at desk
```

Reply sent:

- To: flexxftw12@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Broken chair at 2F-08 [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Broken chair at 2F-08

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 4

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Furniture
Team: Facilities & Maintenance
Due by: 18 Oct, 7:49 AM
Preferred vendor: BrightFurniture Co

Investigation:
Approved vendor on file: BrightFurniture Co; Route to Facilities & Maintenance

Details:
- Item: chair
- Location: 2F-08

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo wo…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: chair [TKT-2026-0001]

```
Dear Rohan Mehta,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: chair [TKT-2026-0001]

```
Dear Rohan Mehta,

Message about TKT-2026-0001 (Broken chair at 2F-08) from Facilities & Maintenance: Is it the armrest or the wheel, and when will you be at your desk?

Regards,
Workplace Team
```

#### test_team_says_where_to_collect_and_the_requester_is_told — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "charger". They wrote: "my laptop charger stopped working, need a new one"
2. it.servicess8989@gmail.com sent an email. Subject: "Re: Work Order: Laptop charger replacement [ITS-2026-0001]". They wrote: "done, new charger ready. collect from IT desk 3rd floor, ask for Rahul"
3. The desk opened ITS-2026-0001 (Laptop charger replacement) — closed as done.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 3 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
5. It wrote to it.servicess8989@gmail.com. Subject: "Work Order: Laptop charger replacement [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Laptop charger replacement Repair. No asset …"
6. It wrote to rohan.mehta@acme.demo. Subject: "Re: charger [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, We have logged your request and assigned it to IT Support. Request: ITS-2026-0001 Subject: Laptop charger replacement Status: Open You will b…"
7. It wrote to rohan.mehta@acme.demo. Subject: "charger [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, Good news - ITS-2026-0001 (Laptop charger replacement) has been taken care of. Note from IT Support: New charger is ready How to collect: IT …"
8. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: Laptop charger replacement [ITS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ITS-2026-0001 Subject: Laptop charger replacement Completed by IT Support: New charger is ready Record ch…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Laptop charger replacement (RESOLVED, MEDIUM, stage RESOLVED, decision REPAIR_UNKNOWN)

Email received:

- From: rohan.mehta@acme.demo
- Subject: charger

```
my laptop charger stopped working, need a new one
```

- From: it.servicess8989@gmail.com
- Subject: Re: Work Order: Laptop charger replacement [ITS-2026-0001]

```
done, new charger ready. collect from IT desk 3rd floor, ask for Rahul
```

Reply sent:

- To: it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Laptop charger replacement [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Laptop charger replacement

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Laptop / device
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Item: laptop charger

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: charger [ITS-2026-0001]

```
Dear Rohan Mehta,

We have logged your request and assigned it to IT Support.

Request: ITS-2026-0001
Subject: Laptop charger replacement
Status: Open

You will be updated on this thread when the work is complete.
No asset record matched this request at your branch, so warranty and repair history were not applied.

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: charger [ITS-2026-0001]

```
Dear Rohan Mehta,

Good news - ITS-2026-0001 (Laptop charger replacement) has been taken care of.
Note from IT Support: New charger is ready
How to collect: IT desk, 3rd floor - ask for Rahul

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Laptop charger replacement [ITS-2026-0001]

```
Dear Team,

Please note the following update.

Request: ITS-2026-0001
Subject: Laptop charger replacement

Completed by IT Support: New charger is ready

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Laptop / device
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Item: laptop charger


Regards,
Workplace Team
```

#### test_company_default_pickup_is_used_when_the_team_does_not_say — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "charger". They wrote: "my laptop charger stopped working, need a new one"
2. it.servicess8989@gmail.com sent an email. Subject: "Re: Work Order: Laptop charger replacement [ITS-2026-0001]". They wrote: "charger replaced"
3. The desk opened ITS-2026-0001 (Laptop charger replacement) — closed as done.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 3 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
5. It wrote to it.servicess8989@gmail.com. Subject: "Work Order: Laptop charger replacement [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Laptop charger replacement Repair. No asset …"
6. It wrote to rohan.mehta@acme.demo. Subject: "Re: charger [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, We have logged your request and assigned it to IT Support. Request: ITS-2026-0001 Subject: Laptop charger replacement Status: Open You will b…"
7. It wrote to rohan.mehta@acme.demo. Subject: "charger [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, Good news - ITS-2026-0001 (Laptop charger replacement) has been taken care of. Note from IT Support: Charger replaced How to collect: IT help…"
8. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: Laptop charger replacement [ITS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ITS-2026-0001 Subject: Laptop charger replacement Completed by IT Support: Charger replaced Record check:…"
9. It wrote to it.servicess8989@gmail.com. Subject: "Work Order: Laptop charger replacement [ITS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ITS-2026-0001 Subject: Laptop charger replacement Thanks for completing this. To close it as verified, pl…"
10. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Laptop charger replacement (RESOLVED, MEDIUM, stage RESOLVED, decision REPAIR_UNKNOWN)

Email received:

- From: rohan.mehta@acme.demo
- Subject: charger

```
my laptop charger stopped working, need a new one
```

- From: it.servicess8989@gmail.com
- Subject: Re: Work Order: Laptop charger replacement [ITS-2026-0001]

```
charger replaced
```

Reply sent:

- To: it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Laptop charger replacement [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Laptop charger replacement

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Laptop / device
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Item: laptop charger

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: charger [ITS-2026-0001]

```
Dear Rohan Mehta,

We have logged your request and assigned it to IT Support.

Request: ITS-2026-0001
Subject: Laptop charger replacement
Status: Open

You will be updated on this thread when the work is complete.
No asset record matched this request at your branch, so warranty and repair history were not applied.

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: charger [ITS-2026-0001]

```
Dear Rohan Mehta,

Good news - ITS-2026-0001 (Laptop charger replacement) has been taken care of.
Note from IT Support: Charger replaced
How to collect: IT helpdesk, 2nd floor, 10 AM - 6 PM

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Laptop charger replacement [ITS-2026-0001]

```
Dear Team,

Please note the following update.

Request: ITS-2026-0001
Subject: Laptop charger replacement

Completed by IT Support: Charger replaced

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Laptop / device
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Item: laptop charger


Regards,
Workplace Team
```

- To: it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Laptop charger replacement [ITS-2026-0001]

```
Dear Team,

Please note the following update.

Request: ITS-2026-0001
Subject: Laptop charger replacement

Thanks for completing this. To close it as verified, please reply with what was done and the asset tag / ticket number if any (or attach a photo).

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Laptop / device
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Item: laptop charger


Regards,
Workplace Team
```

#### test_pickup_found_without_ai_from_the_team_reply — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "charger". They wrote: "my laptop charger stopped working, need a new one"
2. it.servicess8989@gmail.com sent an email. Subject: "Re: Work Order: Laptop charger replacement [ITS-2026-0001]". They wrote: "done - charger ready, pick it up from the IT store room on 1st floor"
3. The desk opened ITS-2026-0001 (Laptop charger replacement) — closed as done.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 3 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
5. It wrote to it.servicess8989@gmail.com. Subject: "Work Order: Laptop charger replacement [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Laptop charger replacement Repair. No asset …"
6. It wrote to rohan.mehta@acme.demo. Subject: "Re: charger [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, We have logged your request and assigned it to IT Support. Request: ITS-2026-0001 Subject: Laptop charger replacement Status: Open You will b…"
7. It wrote to rohan.mehta@acme.demo. Subject: "charger [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, Good news - ITS-2026-0001 (Laptop charger replacement) has been taken care of. Note from IT Support: charger ready, pick it up from the IT st…"
8. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: Laptop charger replacement [ITS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ITS-2026-0001 Subject: Laptop charger replacement Completed by IT Support: charger ready, pick it up from…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Laptop charger replacement (RESOLVED, MEDIUM, stage RESOLVED, decision REPAIR_UNKNOWN)

Email received:

- From: rohan.mehta@acme.demo
- Subject: charger

```
my laptop charger stopped working, need a new one
```

- From: it.servicess8989@gmail.com
- Subject: Re: Work Order: Laptop charger replacement [ITS-2026-0001]

```
done - charger ready, pick it up from the IT store room on 1st floor
```

Reply sent:

- To: it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Laptop charger replacement [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Laptop charger replacement

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Laptop / device
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Item: laptop charger

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: charger [ITS-2026-0001]

```
Dear Rohan Mehta,

We have logged your request and assigned it to IT Support.

Request: ITS-2026-0001
Subject: Laptop charger replacement
Status: Open

You will be updated on this thread when the work is complete.
No asset record matched this request at your branch, so warranty and repair history were not applied.

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: charger [ITS-2026-0001]

```
Dear Rohan Mehta,

Good news - ITS-2026-0001 (Laptop charger replacement) has been taken care of.
Note from IT Support: charger ready, pick it up from the IT store room on 1st floor

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Laptop charger replacement [ITS-2026-0001]

```
Dear Team,

Please note the following update.

Request: ITS-2026-0001
Subject: Laptop charger replacement

Completed by IT Support: charger ready, pick it up from the IT store room on 1st floor

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Laptop / device
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Item: laptop charger


Regards,
Workplace Team
```

#### test_approver_can_say_where_to_collect — PASSED

What happened:

1. rohan.mehta@acme.demo sent an email. Subject: "access card". They wrote: "I lost my access card, please issue a new one"
2. it.servicess8989@gmail.com sent an email. Subject: "Re: Ops Decision: Replacement access card [ITS-2026-0001]". They wrote: "approved, collect from reception tomorrow after 11 am"
3. The desk opened ITS-2026-0001 (Replacement access card) — handed to the team and still open.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 3 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
5. It wrote to skcbsa1221@gmail.com, it.servicess8989@gmail.com. Subject: "Ops Decision: Replacement access card [ITS-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: ITS-2026-0001 Subject: Replacement access card Needs your approval - access card req…"
6. It wrote to rohan.mehta@acme.demo. Subject: "Re: access card [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, Your request has been logged and sent for approval. Request: ITS-2026-0001 Subject: Replacement access card You will be updated on this threa…"
7. It wrote to it.servicess8989@gmail.com. Subject: "Work Order: Replacement access card [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Replacement access card Repair. No asset rec…"
8. It wrote to rohan.mehta@acme.demo. Subject: "access card [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, Request ITS-2026-0001 (Replacement access card) is approved and assigned to IT Support. You will be updated on this thread when the work is c…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Replacement access card (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR_UNKNOWN)

Email received:

- From: rohan.mehta@acme.demo
- Subject: access card

```
I lost my access card, please issue a new one
```

- From: it.servicess8989@gmail.com
- Subject: Re: Ops Decision: Replacement access card [ITS-2026-0001]

```
approved, collect from reception tomorrow after 11 am
```

Reply sent:

- To: skcbsa1221@gmail.com, it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Replacement access card [ITS-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: ITS-2026-0001
Subject: Replacement access card

Needs your approval - access card requests need admin sign-off

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Access card / ID
Team: IT Support

Details:
- Issue: lost access card

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: access card [ITS-2026-0001]

```
Dear Rohan Mehta,

Your request has been logged and sent for approval.

Request: ITS-2026-0001
Subject: Replacement access card

You will be updated on this thread once a decision is recorded.

Regards,
Workplace Team
```

- To: it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Replacement access card [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Replacement access card

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Rohan Mehta <rohan.mehta@acme.demo>
Type: Access card / ID
Team: IT Support
Due by: 18 Oct, 7:49 AM

Details:
- Issue: lost access card

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <the card number issued or access granted>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The…
```

- To: rohan.mehta@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: access card [ITS-2026-0001]

```
Dear Rohan Mehta,

Request ITS-2026-0001 (Replacement access card) is approved and assigned to IT Support. You will be updated on this thread when the work is complete.
Once it's ready, you can collect it: collect from reception tomorrow after 11 am

Regards,
Workplace Team
```

### test_no_resource_flow.py

9 cases, 0 failed.

#### test_detect_larger_venue_choice — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_detect_split_and_different_time — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_greeting_never_dear_there — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_short_subject_drops_gemini_narrative — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_diagnose_equipment_not_fake_capacity — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_diagnose_true_capacity — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_open_request_delta — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_visitor_names_with_emdash_and_no_bare_special_access — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_no_resource_choice_acks_without_resending_menu — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 80 on 22 September 2026) — still open.
2. It wrote to ops.lead@company.com. Subject: "No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Ops Lead, No room fits 80 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40 o…"
3. It wrote to ops.lead@company.com. Subject: "Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]". The message starts: "Dear Ops Lead, Thanks — we've recorded your choice: Escalate for a larger venue / off-site option. Our ops team will take it from here and follow up on this ca…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 80 on 22 September 2026 (ACTIVE, MEDIUM)

Reply sent:

- To: ops.lead@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Ops Lead,

No room fits 80 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

- To: ops.lead@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Choice Noted: Meeting for 80 on 22 September 2026 at 2:00 PM–5:00 PM (3.0h) [ROOM-2026-0001]

```
Dear Ops Lead,

Thanks — we've recorded your choice: Escalate for a larger venue / off-site option.
Our ops team will take it from here and follow up on this case.

Also noted:
- translator
- orchestrator role: module_helper

Case: ROOM-2026-0001
```

### test_ops_resolution.py

5 cases, 1 failed.

#### test_ac_case_writes_ledger_and_plan_without_gemini — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "AC issue". They wrote: "AC not working in 4th floor bay near pantry, very hot"
2. The desk opened TKT-2026-0001 (AC not working in 4th floor bay near pantry, very hot) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to ops-desk@example.com. Subject: "Work Order: AC not working in 4th floor bay near pantry, very hot [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: AC not working in 4th floor bay near pantry,…"
5. It wrote to arjun.singh@acme.demo. Subject: "Re: AC issue [TKT-2026-0001]". The message starts: "Hi Arjun, Thanks for letting us know. I've logged this as TKT-2026-0001 and passed it to the right team - we'll keep you posted here. Workplace Team"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: AC not working in 4th floor bay near pantry, very hot (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: AC issue

```
AC not working in 4th floor bay near pantry, very hot
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: AC not working in 4th floor bay near pantry, very hot [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: AC not working in 4th floor bay near pantry, very hot

Repair This item. Repairs on record: 0 of 6.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Air conditioning
Team: Facilities & Maintenance
Due by: 18 Oct, 7:49 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

What they asked: AC not working in 4th floor bay near pantry, very hot

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue:…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: AC issue [TKT-2026-0001]

```
Hi Arjun,

Thanks for letting us know. I've logged this as TKT-2026-0001 and passed it to the right team - we'll keep you posted here.

Workplace Team
```

#### test_team_done_with_amount_records_spend — FAILED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "AC". They wrote: "AC not cooling in 4th floor bay"
2. Ops <ops-desk@example.com> sent an email. Subject: "Re: Work Order: AC not cooling in bay 4 [TKT-2026-0001]". They wrote: "done, compressor replaced, INR 12500"
3. The desk opened TKT-2026-0001 (AC not cooling in bay 4) — closed as done.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
5. It wrote to ops-desk@example.com. Subject: "Work Order: AC not cooling in bay 4 [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: AC not cooling in bay 4 Repair This item. Re…"
6. It wrote to arjun.singh@acme.demo. Subject: "Re: AC [TKT-2026-0001]". The message starts: "Logged as TKT-2026-0001."
7. It wrote to arjun.singh@acme.demo. Subject: "AC [TKT-2026-0001]". The message starts: "Dear Arjun Singh, Good news - TKT-2026-0001 (AC not cooling in bay 4) has been taken care of. Note from Facilities & Maintenance: compressor replaced, INR 1250…"
8. Result: this test failed. The replies above were still written, and the failure is noted at the end of this case.


Case state:

- TKT-2026-0001: AC not cooling in bay 4 (RESOLVED, MEDIUM, stage RESOLVED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: AC

```
AC not cooling in 4th floor bay
```

- From: Ops <ops-desk@example.com>
- Subject: Re: Work Order: AC not cooling in bay 4 [TKT-2026-0001]

```
done, compressor replaced, INR 12500
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: AC not cooling in bay 4 [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: AC not cooling in bay 4

Repair This item. Repairs on record: 0 of 6.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Air conditioning
Team: Facilities & Maintenance
Due by: 18 Oct, 7:49 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: 4th floor bay
- Issue: AC not cooling

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot pr…
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: AC [TKT-2026-0001]

```
Logged as TKT-2026-0001.
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: AC [TKT-2026-0001]

```
Dear Arjun Singh,

Good news - TKT-2026-0001 (AC not cooling in bay 4) has been taken care of.
Note from Facilities & Maintenance: compressor replaced, INR 12500

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

Failure:

```
E   AssertionError: assert 'SPEND_RECORDED' in ['CASE_OPENED', 'PLAN_PROPOSED', 'WORK_ORDER_SENT', 'TEAM_DONE']
```

#### test_admin_spend_question_answers_from_ledger — PASSED

What happened:

1. ops-desk@example.com sent an email. Subject: "Spend question". They wrote: "How much did FACILITIES spend in the last 30 days?"
2. It wrote to ops-desk@example.com. Subject: "Operations report: all branches". The message starts: "Dear Colleague, Operational spend report Period: last 30 days Scope: all branches Recorded spend: INR 4,200.00 Amount rows: 1 (from 1 related records) These am…"
3. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: ops-desk@example.com
- Subject: Spend question

```
How much did FACILITIES spend in the last 30 days?
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Operations report: all branches

```
Dear Colleague,

Operational spend report

Period: last 30 days
Scope: all branches
Recorded spend: INR 4,200.00
Amount rows: 1 (from 1 related records)

These amounts are reported operational figures. They are not payment records.

By branch:
- Unassigned: INR 4,200.00

Top lines:
- 2026-10-17 FAC-2026-0001 INR 4,200 — HVAC parts for FAC-2026-0001

Regards,
Workplace Team
```

#### test_duplicate_open_ac_links_instead_of_second_dispatch — PASSED

What happened:

1. arjun.singh@acme.demo sent an email. Subject: "AC bay". They wrote: "AC not working in 4th floor bay near pantry"
2. priya.sharma@acme.demo sent an email. Subject: "AC bay again". They wrote: "AC not working in 4th floor bay near pantry, very hot"
3. The desk opened TKT-2026-0001 (AC not working in 4th floor bay near pantry) — handed to the team and still open; TKT-2026-0002 (AC not working in 4th floor bay near pantry) — closed.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
5. It wrote to ops-desk@example.com. Subject: "Work Order: AC not working in 4th floor bay near pantry [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: AC not working in 4th floor bay near pantry …"
6. It wrote to arjun.singh@acme.demo. Subject: "Re: AC bay [TKT-2026-0001]". The message starts: "Logged TKT-2026-0001."
7. It wrote to priya.sharma@acme.demo. Subject: "Re: AC bay again [TKT-2026-0001]". The message starts: "Dear Priya Sharma, This report has been linked to open request TKT-2026-0001. The assigned team will continue on that request. Regards, Workplace Team"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: AC not working in 4th floor bay near pantry (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)
- TKT-2026-0002: AC not working in 4th floor bay near pantry (CLOSED, MEDIUM, stage LINKED, decision REPAIR)

Email received:

- From: arjun.singh@acme.demo
- Subject: AC bay

```
AC not working in 4th floor bay near pantry
```

- From: priya.sharma@acme.demo
- Subject: AC bay again

```
AC not working in 4th floor bay near pantry, very hot
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: AC not working in 4th floor bay near pantry [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: AC not working in 4th floor bay near pantry

Repair This item. Repairs on record: 0 of 6.
(No Facilities & Maintenance contact set yet - sent to you. Add it in Company setup.)

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Arjun Singh <arjun.singh@acme.demo>
Type: Air conditioning
Team: Facilities & Maintenance
Due by: 18 Oct, 7:49 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: 4th floor bay near pantry
- Issue: AC not working

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is …
```

- To: arjun.singh@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: AC bay [TKT-2026-0001]

```
Logged TKT-2026-0001.
```

- To: priya.sharma@acme.demo
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: AC bay again [TKT-2026-0001]

```
Dear Priya Sharma,

This report has been linked to open request TKT-2026-0001. The assigned team will continue on that request.

Regards,
Workplace Team
```

#### test_resolution_heuristic_fallback_when_gemini_off — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- FAC-2099-0999: AC failure (ACTIVE, MEDIUM)

No email was stored for this case.

### test_outcome_reducer.py

4 cases, 0 failed.

#### test_informal_reply_completes_against_prior_snapshot — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_reducer_does_not_blank_prior_time — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_heuristic_does_not_invent_one_visitor — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_stale_checklist_cleared_after_reduce — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_pdf_invoice_extract.py

5 cases, 0 failed.

#### test_scrape_invoice_fields_from_text — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_extract_pdf_text_roundtrip — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_persist_pdf_and_scrape — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_cloudmailin_keeps_attachment_content — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_intake_stores_scraped_fields_not_bytes — PASSED

What happened:

1. vendor@supplier.com sent an email. Subject: "Invoice INV-55". They wrote: "Please process the attached invoice."
2. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: vendor@supplier.com
- Subject: Invoice INV-55

```
Please process the attached invoice.
```

### test_phase2_contract.py

6 cases, 0 failed.

#### test_field_contract_separates_understood_assumed_missing — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_operator_override_sets_user_confirmed_and_clears_gap — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_heuristic_fill_marked_candidate_provenance — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_record_suppressed_writes_reason_and_history — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_requirement_split_confirmed_upper_unconfirmed_lower — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_extracted_explicit_none_stays_in_confirmed — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_phases_3_5.py

6 cases, 0 failed.

#### test_versioned_policy_buffers_and_auto_book — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_no_resource_alternatives_structured — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_active_modules_selective — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_generic_pattern_onboarding_shape — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_golden_eval_pass_rate — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_sla_tick_marks_overdue — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_pipeline_contract.py

3 cases, 0 failed.

#### test_incomplete_meeting_event_stays_communication_not_completed — PASSED

What happened:

1. arun.kumar@company.com sent an email. Subject: "Meeting room required for 18 September". They wrote: "Please book a meeting room for 18 September."
2. The desk opened ROOM-2026-0001 (Meeting room required for 18 September) — still open.
3. It wrote to arun.kumar@company.com. Subject: "Information required: Request registered — details needed [ROOM-2026-0001]". The message starts: "Dear Arun Kumar, Thanks for your meeting-room request — it's registered as ROOM-2026-0001. Here's what I have so far: - Date: 2027-09-18 To lock in a room I ju…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting room required for 18 September (ACTIVE, MEDIUM)

Email received:

- From: arun.kumar@company.com
- Subject: Meeting room required for 18 September

```
Please book a meeting room for 18 September.
```

Reply sent:

- To: arun.kumar@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_REQUIRED
- Subject: Information required: Request registered — details needed [ROOM-2026-0001]

```
Dear Arun Kumar,

Thanks for your meeting-room request — it's registered as ROOM-2026-0001.

Here's what I have so far:

- Date: 2027-09-18

To lock in a room I just need:

- How many people will attend in person?
- What time slot do you need (e.g. 10:00 AM–1:00 PM, or 2:00 PM for 1 hour)?
- Which office or building is required? Your primary office is Corporate Office, Gurugram.
- Meeting type: internal, client/vendor, interview, training, confidential, or other?

Also worth a quick check:

- Hybrid / AV: not answered
- Presentation display: not answered
- Catering / amenities: not answered
- Special access / security: not answered
- Confidentiality: not answered

Just reply to this email with the details.
```

#### test_follow_up_clarification_keyed_by_event_id — PASSED

What happened:

1. arun.kumar@company.com sent an email. Subject: "Need a meeting room". They wrote: "Please book a meeting room for 18 September."
2. arun.kumar@company.com sent an email. Subject: "Re: [INFORMATION REQUIRED] Need a meeting room". They wrote: "internal , non veg , rahul and aman"
3. The desk opened ROOM-2026-0001 (Re: [INFORMATION REQUIRED] Need a meeting room) — still open.
4. It wrote to arun.kumar@company.com. Subject: "Information required: Request registered — details needed [ROOM-2026-0001]". The message starts: "Dear Arun Kumar, Thanks for your meeting-room request — it's registered as ROOM-2026-0001. Here's what I have so far: - Date: 2027-09-18 To lock in a room I ju…"
5. It wrote to arun.kumar@company.com. Subject: "Information required: Additional details needed [ROOM-2026-0001]". The message starts: "Dear Arun Kumar, Here's what I have so far: - Date: 2027-09-18 - Meeting type: internal meeting - Location preference: Corporate Office, Gurugram - Dietary: no…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Re: [INFORMATION REQUIRED] Need a meeting room (ACTIVE, MEDIUM)

Email received:

- From: arun.kumar@company.com
- Subject: Need a meeting room

```
Please book a meeting room for 18 September.
```

- From: arun.kumar@company.com
- Subject: Re: [INFORMATION REQUIRED] Need a meeting room

```
internal , non veg , rahul and aman
```

Reply sent:

- To: arun.kumar@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_REQUIRED
- Subject: Information required: Request registered — details needed [ROOM-2026-0001]

```
Dear Arun Kumar,

Thanks for your meeting-room request — it's registered as ROOM-2026-0001.

Here's what I have so far:

- Date: 2027-09-18

To lock in a room I just need:

- How many people will attend in person?
- What time slot do you need (e.g. 10:00 AM–1:00 PM, or 2:00 PM for 1 hour)?
- Which office or building is required? Your primary office is Corporate Office, Gurugram.
- Meeting type: internal, client/vendor, interview, training, confidential, or other?

Also worth a quick check:

- Hybrid / AV: not answered
- Presentation display: not answered
- Catering / amenities: not answered
- Special access / security: not answered
- Confidentiality: not answered

Just reply to this email with the details.
```

- To: arun.kumar@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_REQUIRED
- Subject: Information required: Additional details needed [ROOM-2026-0001]

```
Dear Arun Kumar,

Here's what I have so far:

- Date: 2027-09-18
- Meeting type: internal meeting
- Location preference: Corporate Office, Gurugram
- Dietary: non-vegetarian

To lock in a room I just need:

- How many people will attend in person?
- What time slot do you need (e.g. 10:00 AM–1:00 PM, or 2:00 PM for 1 hour)?

Also worth a quick check:

- Hybrid / AV: not answered
- Presentation display: not answered
- Catering / amenities: not answered
- Special access / security: not answered
- Confidentiality: not answered

If you have them handy, please also share (these won't hold up the booking):

- Cost centre and approving department head (for the chargeable items).

No separate approval is needed for meeting room, drinking water and standard bottles. Cost approval will cover only catering (menu to be confirmed).

Just reply to this email with the details.
```

#### test_no_resource_event_not_marked_completed — PASSED

What happened:

1. big.team@company.com sent an email. Subject: "Need a meeting room for all hands". They wrote: "Book a meeting room for 80 people on 22 September 2026 from 2pm to 5pm. Internal meeting at Corporate Office. No visitors. No catering. Display required."
2. The desk opened ROOM-2026-0001 (Meeting for 80 on 22 september at 2pm–5pm. (3.0h)) — still open.
3. It wrote to big.team@company.com. Subject: "No Room Available: Meeting for 80 on 22 september at 2pm–5pm. (3.0h) [ROOM-2026-0001]". The message starts: "Dear Big Team, No room fits 80 people in person (largest inventory room holds 40). Please reply with one of these options: - Reduce in-person headcount to 40 o…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 80 on 22 september at 2pm–5pm. (3.0h) (ACTIVE, MEDIUM)

Email received:

- From: big.team@company.com
- Subject: Need a meeting room for all hands

```
Book a meeting room for 80 people on 22 September 2026 from 2pm to 5pm. Internal meeting at Corporate Office. No visitors. No catering. Display required.
```

Reply sent:

- To: big.team@company.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: No Room Available: Meeting for 80 on 22 september at 2pm–5pm. (3.0h) [ROOM-2026-0001]

```
Dear Big Team,

No room fits 80 people in person (largest inventory room holds 40).

Please reply with one of these options:
- Reduce in-person headcount to 40 or fewer
- Try a different date or start time
- Escalate for a larger venue / off-site option
- Split into two rooms (~40 + 40) — Auditorium A + Learning Studio A + Conference Room 12A are free

Case: ROOM-2026-0001
```

### test_record_decisions.py

6 cases, 0 failed.

#### test_ac_in_room_4_uses_that_units_warranty — PASSED

What happened:

1. The request was: please fix the AC in room 4.
2. The system looked up that office and found the AC kept for room 4.
3. The warranty end date on that AC was 1 June 2027, so the warranty was still valid. It had been repaired 0 times.
4. The result was: repair it under warranty. No email was written in this test, because the test stopped once that decision was made. On a normal mail, that decision is written into the work order.


No email was stored for this case.

#### test_fan_repaired_past_the_company_limit_is_a_replacement — PASSED

What happened:

1. The request was: please fix the fan in room 4.
2. The system looked up that fan. The company rule says replace an electrical item after it has been repaired 50 times.
3. The records showed this fan had already been repaired 50 times. Its warranty had ended on 1 January 2020, and there was no AMC to use.
4. The result was: do not repair it again. Replace it. No email was written in this test. On a normal mail, the work order would say replace, not repair.


No email was stored for this case.

#### test_unknown_room_does_not_invent_a_repair_count — PASSED

What happened:

1. The request was only: the AC is warm. No room and no office were given.
2. The system looked for a matching AC and did not find one.
3. It did not guess a warranty, an AMC, or a repair count.
4. The result was: treat it as a repair, but say the history is unknown.


No email was stored for this case.

#### test_repeat_housekeeping_escalates — PASSED

What happened:

1. The request was: please clean room 2 again.
2. The system looked up room 2 at that office. Cleaning there had already been finished 4 times. The limit is 4.
3. The result was: do not treat this as an ordinary repeat. Raise it.


No email was stored for this case.

#### test_second_laptop_needs_approval — PASSED

What happened:

1. The person asked for another laptop.
2. The records showed they already had a laptop.
3. The result was: do not issue another one until someone approves it.


No email was stored for this case.

#### test_expired_stock_is_not_issued — PASSED

What happened:

1. The request was for tea bags.
2. The stock record for tea bags at that office had an expiry date of 1 January 2020.
3. The result was: do not issue them. They are past expiry.


No email was stored for this case.

### test_review_accept.py

32 cases, 0 failed.

#### test_meeting_room_gaps_complete — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_meeting_room_gaps_missing_date — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_meeting_room_gaps_only_core_blocks — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_route_sensitive_not_overwritten_by_low_confidence — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_questions_only_ask_missing_when_facts_known — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_heuristic_parses_participants_and_not_false_confirm — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_llm_service_refine_does_not_invent_visitor_count — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_refine_prefers_gemini_entities_over_heuristic_guesses — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_bare_internal_maps_to_meeting_type — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_heuristic_reply_with_prior_facts_completes — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_heuristic_parses_typo_employees_and_visitor_names — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_extraction_result_coerces_lowercase_priority — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_gemini_failover_uses_secondary_after_model_failures — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_gemini_fills_blanks_with_heuristic_candidates — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Gemini succeeds but leaves typo headcount blank — heuristic candidates fill only unknowns.

No email was stored for this case.

#### test_confirm_reply_parses_parking_and_dietary_split — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_display_name_from_from_header — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_kapil_style_golden_email_remaining_only_ask — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Golden regression: rich informal mail → understand most facts, ask only gaps.

No email was stored for this case.

#### test_gemini_endpoint_order_includes_secondary_key — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_llm_service_falls_back_after_gemini_503_exhausted — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_fact_delta_applied_by_refine — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_informal_reply_via_llm_service_against_snapshot — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_parse_messy_signals_newline_range_and_ish_time — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_heuristic_messy_mail_headcount_and_bare_time_range — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_gemini_blank_delta_filled_by_grounded_messy_parse — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

ROOM-2026-0003 failure mode: Gemini answers but skips headcount/time.

No email was stored for this case.

#### test_confirm_reply_persists_spaced_plate_and_extra_visitor — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

ROOM-2026-0005 failure: confirm + plate + extra visitor must persist.

No email was stored for this case.

#### test_unmapped_ask_is_kept_on_open_requests — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_expected_participants_around_n_is_attendees — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_yahoo_inline_answers_are_not_lost_and_not_false_confirm — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_five_employee_on_special_access_does_not_replace_headcount — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_interpreter_view_keeps_quote_for_the_model — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_compact_interpreter_state_drops_platform_noise — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_gemini_reads_mail_like_chat_not_a_form — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_reviews_inbox.py

1 cases, 0 failed.

#### test_reviews_inbox_matches_waiting_on_you_kpi — PASSED

What happened:

1. ops@acme.demo sent an email. Subject: "Inbox review". They wrote: "Please decide"
2. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-INBOX-OPEN: Open catering case (ACTIVE, MEDIUM)
- ROOM-INBOX-CLOSED: Closed leftover approval (CLOSED, MEDIUM)
- ROOM-INBOX-CONFIRM: Waiting on room confirm (ACTIVE, MEDIUM)

Email received:

- From: ops@acme.demo
- Subject: Inbox review

```
Please decide
```

### test_scenarios.py

16 cases, 0 failed.

#### test_incomplete_joining_email_clarification_no_duplicate — PASSED

What happened:

1. hr@acme.demo sent an email. Subject: "New joiner starting soon". They wrote: "Please arrange workplace readiness for a new employee joining tomorrow."
2. hr@acme.demo sent an email. Subject: "Re: New joiner". They wrote: "Employee name is Riya Shah, department Engineering, manager Priya Manager, hybrid work model."
3. The desk opened ONB-2026-0001 (Re: New joiner) — still open.
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ONB-2026-0001: Re: New joiner (ACTIVE, MEDIUM)

Email received:

- From: hr@acme.demo
- Subject: New joiner starting soon

```
Please arrange workplace readiness for a new employee joining tomorrow.
```

- From: hr@acme.demo
- Subject: Re: New joiner

```
Employee name is Riya Shah, department Engineering, manager Priya Manager, hybrid work model.
```

#### test_no_permanent_seat_blocks_only_seat_task — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- ONB-2026-0001: New joiner — no permanent seat (PARTIALLY_READY, MEDIUM)

No email was stored for this case.

#### test_parking_occupied — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- PARK-2026-0001: My parking is occupied (ACTIVE, MEDIUM)

No email was stored for this case.

#### test_chair_missing_separate_tasks — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- FURN-2026-0001: Chair missing (ACTIVE, MEDIUM)

No email was stored for this case.

#### test_vendor_escalation_unverified — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- VND-2026-0001: Vendor substituted expired goods (ACTIVE, MEDIUM)

No email was stored for this case.

#### test_matched_invoice_no_auto_payment — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- INV-2026-0001: Invoice for PO (ACTIVE, MEDIUM)

No email was stored for this case.

#### test_invoice_quantity_mismatch — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- INV-2026-0001: Invoice mismatch (ACTIVE, MEDIUM)

No email was stored for this case.

#### test_duplicate_invoice_blocked — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- INV-2026-0001: Dup invoice (ACTIVE, MEDIUM)
- INV-2026-0002: Dup invoice (PARTIALLY_READY, MEDIUM)

No email was stored for this case.

#### test_bank_details_change_requires_verification — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- INV-2026-0001: Please update bank details and pay (ACTIVE, MEDIUM)

No email was stored for this case.

#### test_low_confidence_routes_to_clarification_or_review — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_task_completed_without_evidence_blocked — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- FURN-2026-0001: Chair missing (ACTIVE, MEDIUM)

No email was stored for this case.

#### test_duplicate_email_idempotency — PASSED

What happened:

1. hr@acme.demo sent an email. Subject: "Hi". They wrote: "Hello"
2. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: hr@acme.demo
- Subject: Hi

```
Hello
```

#### test_api_login_and_kpis — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_meeting_room_proposes_then_confirms — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 5 on 15th october at 3 pm–7pm (4.0h)) — still open.
2. It wrote to employee1@acme.demo. Subject: "Confirm Booking: Meeting for 5 on 15th october at 3 pm–7pm (4.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 5 - Date: 15th o…"
3. It wrote to employee1@acme.demo. Subject: "Booking Confirmed: Meeting for 5 on 15th october at 3 pm–7pm (4.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 1, Your meeting room booking is confirmed. Room: Huddle Room F2-R2 Case: ROOM-2026-0001 Hold window: 3 pm (setup 30m earlier) – 7pm (+15m release…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 5 on 15th october at 3 pm–7pm (4.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 5 on 15th october at 3 pm–7pm (4.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 5
- Date: 15th october
- Time: 3 pm – 7pm
- Meeting type: workshop
- Location preference: Corporate Office
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Catering / amenities: none
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee1@acme.demo
- From: workplace-desk@localhost
- Type: COMPLETED
- Subject: Booking Confirmed: Meeting for 5 on 15th october at 3 pm–7pm (4.0h) [ROOM-2026-0001]

```
Dear Employee 1,

Your meeting room booking is confirmed.

Room: Huddle Room F2-R2
Case: ROOM-2026-0001
Hold window: 3 pm (setup 30m earlier) – 7pm (+15m release)

No visitor, parking, catering or billing modules were activated.
No separate approval is needed for meeting room.
After the meeting, just reply "satisfied" and we'll close it off.
```

#### test_meeting_room_addon_before_confirm_updates_proposal — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 4 on tomorrow at 10 am (2.0h)) — still open.
2. It wrote to employee3@acme.demo. Subject: "Confirm Booking: Meeting for 4 on tomorrow at 10 am (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 3, Good news — I found a room that fits and I'm holding it for you. Room: Huddle Room F2-R2 (seats 6) Your booking: - Attendees: 4 - Date: tomorr…"
3. It wrote to employee3@acme.demo. Subject: "Confirm Booking: Meeting for 4 on tomorrow at 10 am (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 3, Thanks — I've updated your request with the changes. Room: Focus Room 5B (seats 8) Your booking: - Attendees: 4 - Date: tomorrow - Time: 10 am…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 4 on tomorrow at 10 am (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee3@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 4 on tomorrow at 10 am (2.0h) [ROOM-2026-0001]

```
Dear Employee 3,

Good news — I found a room that fits and I'm holding it for you.

Room: Huddle Room F2-R2 (seats 6)

Your booking:
- Attendees: 4
- Date: tomorrow
- Time: 10 am (2.0h)
- Meeting type: workshop
- Location preference: Corporate Office
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Hybrid / AV: no
- Presentation display: no
- Catering / amenities: none
- Special access / security: none
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

- To: employee3@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 4 on tomorrow at 10 am (2.0h) [ROOM-2026-0001]

```
Dear Employee 3,

Thanks — I've updated your request with the changes.

Room: Focus Room 5B (seats 8)

Your booking:
- Attendees: 4
- Date: tomorrow
- Time: 10 am (2.0h)
- Meeting type: workshop
- Hybrid / AV: yes — video/AV needed
- Presentation display: no
- Location preference: Corporate Office
- Catering / amenities: coffee and snacks
- Dietary: 4 vegetarian
- Confidentiality: standard
- Also requested: orchestrator role: module_helper
- Also requested: spine template: MEETING_ROOM

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

#### test_meeting_room_full_checklist_with_catering_proposes — PASSED

What happened:

1. The desk opened ROOM-2026-0001 (Meeting for 4 on tomorrow at 10 am–7pm (2.0h)) — still open.
2. It wrote to employee2@acme.demo. Subject: "Confirm Booking: Meeting for 4 on tomorrow at 10 am–7pm (2.0h) [ROOM-2026-0001]". The message starts: "Dear Employee 2, Good news — I found a room that fits and I'm holding it for you. Room: Focus Room 5B (seats 8) Layout: boardroom Your booking: - Attendees: 4 …"
3. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ROOM-2026-0001: Meeting for 4 on tomorrow at 10 am–7pm (2.0h) (ACTIVE, MEDIUM)

Reply sent:

- To: employee2@acme.demo
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Confirm Booking: Meeting for 4 on tomorrow at 10 am–7pm (2.0h) [ROOM-2026-0001]

```
Dear Employee 2,

Good news — I found a room that fits and I'm holding it for you.

Room: Focus Room 5B (seats 8)
Layout: boardroom

Your booking:
- Attendees: 4
- Date: tomorrow
- Time: 10 am – 7pm
- Meeting type: external client pitch
- Hybrid / AV: yes — video/AV needed
- Location preference: boardroom
- Catering / amenities: requested
- Dietary: 4 vegetarian
- Special access / security: required
- Also requested: orchestrator role: module_helper

I've set these for you — reply if any should change:
- Presentation display: no
- Confidentiality: standard

Reply "confirm" to lock it in — I'm holding the room for 24 hours, after which it's released for others.
Need anything else (catering, AV, parking, a different floor)? Just mention it in your reply.

Case: ROOM-2026-0001
```

### test_schema_sync.py

4 cases, 2 failed.

#### test_empty_database_gets_every_table — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_old_database_gets_new_tables_and_columns_and_keeps_rows — FAILED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check failed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check failed.

No email was stored for this case.

Failure:

```
E   sqlite3.IntegrityError: NOT NULL constraint failed: tenants.default_timezone

The above exception was the direct cause of the following exception:
E   sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) NOT NULL constraint failed: tenants.default_timezone
    [SQL: INSERT INTO tenants (tenant_id, name, region, status, created_at, updated_at) VALUES ('t1', 'Acme', 'IN', 'ACTIVE', '2026-01-01', '2026-01-01')]
    (Background on this error at: https://sqlalche.me/e/20/gkpj)
```

#### test_new_column_with_a_simple_default_fills_existing_rows — FAILED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check failed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check failed.

No email was stored for this case.

Failure:

```
E   sqlite3.IntegrityError: NOT NULL constraint failed: tenants.default_timezone

The above exception was the direct cause of the following exception:
E   sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) NOT NULL constraint failed: tenants.default_timezone
    [SQL: INSERT INTO tenants (tenant_id, name, region, status, created_at, updated_at) VALUES ('t1', 'Acme', 'IN', 'ACTIVE', '2026-01-01', '2026-01-01')]
    (Background on this error at: https://sqlalche.me/e/20/gkpj)
```

#### test_alembic_upgrade_builds_a_fresh_database — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_security_harden.py

8 cases, 0 failed.

#### test_sanitize_api_email_headers_strips_spf_dkim — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_api_intake_strips_forged_auth_headers — PASSED

What happened:

1. ops-desk@example.com sent an email. Subject: "How much did we spend?". They wrote: "How much did FACILITIES spend last 30 days?"
2. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: ops-desk@example.com
- Subject: How much did we spend?

```
How much did FACILITIES spend last 30 days?
```

#### test_ops_analytics_rejects_unverified_sender — PASSED

What happened:

1. ops-desk@example.com sent an email. Subject: "Spend". They wrote: "How much did FACILITIES spend in the last 30 days?"
2. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: ops-desk@example.com
- Subject: Spend

```
How much did FACILITIES spend in the last 30 days?
```

#### test_ops_analytics_accepts_gmail_neutral_spf_from_google — PASSED

What happened:

1. ops-desk@example.com sent an email. Subject: "Spent". They wrote: "How much is the total spent till now"
2. It wrote to ops-desk@example.com. Subject: "Operations report: all branches". The message starts: "Dear Colleague, Operational spend report Period: last 30 days Scope: all branches Recorded spend: INR 800.00 Amount rows: 1 (from 1 related records) These amou…"
3. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: ops-desk@example.com
- Subject: Spent

```
How much is the total spent till now
```

Reply sent:

- To: ops-desk@example.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Operations report: all branches

```
Dear Colleague,

Operational spend report

Period: last 30 days
Scope: all branches
Recorded spend: INR 800.00
Amount rows: 1 (from 1 related records)

These amounts are reported operational figures. They are not payment records.

By branch:
- Unassigned: INR 800.00

Top lines:
- 2026-10-17 — INR 800 — branch paint

Regards,
Workplace Team
```

#### test_branch_admin_spend_stays_on_their_site — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_done_inr_amount_is_read_from_the_raw_reply — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_bootstrap_uses_admin_password_env — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_bootstrap_rejects_weak_password_in_production — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_setup_api.py

13 cases, 2 failed.

#### test_status_shows_env_admin_and_placeholder_departments — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_setup_requires_login — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_setting_department_email_makes_it_the_real_route — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_create_and_deactivate_department — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_bad_department_email_rejected — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_knowledge_upsert_and_delete — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_template_download — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_employee_csv_preview_then_commit — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_department_xlsx_import_updates_existing — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_empty_upload_rejected — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_company_workbook_preview_and_commit — FAILED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check failed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check failed.

No email was stored for this case.

Failure:

```
E   sqlite3.OperationalError: near "SET": syntax error

The above exception was the direct cause of the following exception:
E   sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) near "SET": syntax error
    [SQL: SET LOCAL statement_timeout = '300s']
    (Background on this error at: https://sqlalche.me/e/20/e3q8)
```

#### test_company_ai_json_dump_import — FAILED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check failed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check failed.

No email was stored for this case.

Failure:

```
E   sqlite3.OperationalError: near "SET": syntax error

The above exception was the direct cause of the following exception:
E   sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) near "SET": syntax error
    [SQL: SET LOCAL statement_timeout = '300s']
    (Background on this error at: https://sqlalche.me/e/20/e3q8)
```

#### test_company_template_download — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_smart_mail.py

23 cases, 0 failed.

#### test_seats_include_in_person_visitors — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_twelve_seat_room_rejected_for_twelve_plus_two_visitors — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_summary_merges_visitors_and_drops_noise — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_briefing_shows_signed_name_and_no_duplicate_lines — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_gemini_schema_declares_fact_fields — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_hybrid_reads_free_text — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_new_fact_keys_are_not_open_requests — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_must_keep_tokens_cover_case_room_and_reply_word — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_mail_writer_accepts_faithful_rewrite — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_mail_writer_rejects_rewrite_that_drops_room — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_addon_reply_with_stale_new_request_flag_updates_same_case — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_new_request_flag_on_different_day_spawns_case — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_per_message_flags_do_not_carry_over_from_prior_facts — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_booked_briefing_is_a_short_work_order — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_booked_briefing_uses_latest_counted_catering_and_real_visitor_names — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_visitor_addition_marker_is_short — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_pasted_back_form_reads_as_answers_only — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_room_fit_note_explains_oversized_room_and_missing_vc — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_catering_counts_survive_in_requesters_words — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_live_reply_six_more_visitors_and_diet_split — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_our_subject_tag_is_not_the_requesters_confirm — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_addon_reply_to_offer_is_not_booked_even_if_model_says_confirm — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_platform_bookkeeping_never_becomes_an_open_request — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_test_company.py

19 cases, 0 failed.

#### test_build_is_repeatable — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_company_has_thirty_plus_branches_and_folded_catalogue — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_pune_job_goes_to_pune_facilities_and_their_reply_closes_it — PASSED

What happened:

1. cateringservices4656@gmail.com sent an email. Subject: "AC not cooling". They wrote: "The AC on the 3rd floor is not cooling at all."
2. flexxftw12@gmail.com sent an email. Subject: "Re: Work Order: AC not cooling [TKT-2026-0001]". They wrote: "fixed, gas refilled and tested"
3. The desk opened TKT-2026-0001 (AC not cooling) — closed as done.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 6 repairs. The records did not call for a replacement, so this stayed a normal repair.
5. It wrote to flexxftw12+pune@gmail.com. Subject: "Work Order: AC not cooling [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: AC not cooling Repair This item. Repairs on …"
6. It wrote to cateringservices4656@gmail.com. Subject: "Re: AC not cooling [TKT-2026-0001]". The message starts: "Dear Ananya Rao, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-000…"
7. It wrote to cateringservices4656@gmail.com. Subject: "AC not cooling [TKT-2026-0001]". The message starts: "Dear Ananya Rao, Good news - TKT-2026-0001 (AC not cooling) has been taken care of. Note from Facilities - Pune: Gas refilled and AC tested If anything is stil…"
8. It wrote to skcbsa1221@gmail.com, skcbsa1221+pune@gmail.com. Subject: "Ops Update: AC not cooling [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: AC not cooling Completed by Facilities - Pune: Gas refilled and AC tested Record c…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: AC not cooling (RESOLVED, MEDIUM, stage RESOLVED, decision REPAIR)

Email received:

- From: cateringservices4656@gmail.com
- Subject: AC not cooling

```
The AC on the 3rd floor is not cooling at all.
```

- From: flexxftw12@gmail.com
- Subject: Re: Work Order: AC not cooling [TKT-2026-0001]

```
fixed, gas refilled and tested
```

Reply sent:

- To: flexxftw12+pune@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: AC not cooling [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: AC not cooling

Repair This item. Repairs on record: 0 of 6.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Ananya Rao <cateringservices4656@gmail.com>
Type: Air conditioning
Location: Pune > Pune Hinjewadi
Team: Facilities - Pune
Due by: 18 Oct, 7:50 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities - Pune

Details:
- Location: 3rd floor

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to <email>" to transfer t…
```

- To: cateringservices4656@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: AC not cooling [TKT-2026-0001]

```
Dear Ananya Rao,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities - Pune.

Regards,
Workplace Team
```

- To: cateringservices4656@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: AC not cooling [TKT-2026-0001]

```
Dear Ananya Rao,

Good news - TKT-2026-0001 (AC not cooling) has been taken care of.
Note from Facilities - Pune: Gas refilled and AC tested

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com, skcbsa1221+pune@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: AC not cooling [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: AC not cooling

Completed by Facilities - Pune: Gas refilled and AC tested

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 6

Requester: Ananya Rao <cateringservices4656@gmail.com>
Type: Air conditioning
Location: Pune > Pune Hinjewadi
Team: Facilities - Pune
Due by: 18 Oct, 7:50 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: 3rd floor


Regards,
Workplace Team
```

#### test_chennai_has_no_admin_so_south_admin_takes_it — PASSED

What happened:

1. flexxftw12@gmail.com sent an email. Subject: "Stationery". They wrote: "Need 2 notebooks and a stapler."
2. The desk opened SUP-2026-0001 (Stationery: 2 notebooks, 1 stapler) — handed to the team and still open.
3. It checked the records. Nothing in the records blocked it, so the desk carried on.
4. It wrote to skcbsa1221+south@gmail.com. Subject: "Work Order: Stationery: 2 notebooks, 1 stapler [SUP-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: SUP-2026-0001 Subject: Stationery: 2 notebooks, 1 stapler New work …"
5. It wrote to flexxftw12@gmail.com. Subject: "Re: Stationery [SUP-2026-0001]". The message starts: "Dear Vikram Shetty, We have logged your request and assigned it to Admin - South. Request: SUP-2026-0001 Subject: Stationery: 2 notebooks, 1 stapler Status: Op…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- SUP-2026-0001: Stationery: 2 notebooks, 1 stapler (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: flexxftw12@gmail.com
- Subject: Stationery

```
Need 2 notebooks and a stapler.
```

Reply sent:

- To: skcbsa1221+south@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Stationery: 2 notebooks, 1 stapler [SUP-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: SUP-2026-0001
Subject: Stationery: 2 notebooks, 1 stapler

New work order

Requester: Vikram Shetty <flexxftw12@gmail.com>
Type: Office supplies
Location: Chennai > Chennai OMR
Team: Admin - South
Due by: 18 Oct, 7:50 AM

Details:
- Items: 2 notebooks, 1 stapler

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was delivered and to whom>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
When the item is ready, state where and from whom to collect it (for example, "done - card ready, collect from …
```

- To: flexxftw12@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Stationery [SUP-2026-0001]

```
Dear Vikram Shetty,

We have logged your request and assigned it to Admin - South.

Request: SUP-2026-0001
Subject: Stationery: 2 notebooks, 1 stapler
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

#### test_gurugram_laptop_goes_to_north_it_and_mumbai_to_company_it — PASSED

What happened:

1. it.servicess8989@gmail.com sent an email. Subject: "Laptop". They wrote: "My laptop won't boot since this morning."
2. kshitiz.vishwakarma2003@gmail.com sent an email. Subject: "VPN". They wrote: "VPN keeps disconnecting on my laptop."
3. The desk opened ITS-2026-0001 (Laptop not booting) — handed to the team and still open; ITS-2026-0002 (VPN disconnecting) — handed to the team and still open.
4. It checked the records. Nothing in the records blocked it, so the desk carried on.
5. It wrote to it.servicess8989+north@gmail.com. Subject: "Work Order: Laptop not booting [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Laptop not booting New work order Requester:…"
6. It wrote to it.servicess8989@gmail.com. Subject: "Re: Laptop [ITS-2026-0001]". The message starts: "Dear Neha Kapoor, We have logged your request and assigned it to IT Support - North. Request: ITS-2026-0001 Subject: Laptop not booting Status: Open You will b…"
7. It wrote to it.servicess8989+it@gmail.com. Subject: "Work Order: VPN disconnecting [ITS-2026-0002]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0002 Subject: VPN disconnecting New work order Requester: …"
8. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "Re: VPN [ITS-2026-0002]". The message starts: "Dear Kshitiz Vishwakarma, We have logged your request and assigned it to IT Support. Request: ITS-2026-0002 Subject: VPN disconnecting Status: Open You will be…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Laptop not booting (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)
- ITS-2026-0002: VPN disconnecting (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: it.servicess8989@gmail.com
- Subject: Laptop

```
My laptop won't boot since this morning.
```

- From: kshitiz.vishwakarma2003@gmail.com
- Subject: VPN

```
VPN keeps disconnecting on my laptop.
```

Reply sent:

- To: it.servicess8989+north@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Laptop not booting [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Laptop not booting

New work order

Requester: Neha Kapoor <it.servicess8989@gmail.com>
Type: IT support
Location: Gurugram > Gurugram Cyber City
Team: IT Support - North
Due by: 18 Oct, 7:50 AM

Details:
- Issue: laptop does not boot, black screen
- Time: morning

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or priority is wrong, reply "change team to…
```

- To: it.servicess8989@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Laptop [ITS-2026-0001]

```
Dear Neha Kapoor,

We have logged your request and assigned it to IT Support - North.

Request: ITS-2026-0001
Subject: Laptop not booting
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

- To: it.servicess8989+it@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: VPN disconnecting [ITS-2026-0002]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0002
Subject: VPN disconnecting

New work order

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Network / Wi-Fi
Location: Mumbai > Mumbai BKC
Team: IT Support
Due by: 18 Oct, 7:50 AM

Details:
- Issue: VPN drops every few minutes

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or priority is wrong, reply "change team to <team>", "change type …
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: VPN [ITS-2026-0002]

```
Dear Kshitiz Vishwakarma,

We have logged your request and assigned it to IT Support.

Request: ITS-2026-0002
Subject: VPN disconnecting
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

#### test_visitor_to_another_branch_is_served_there — PASSED

What happened:

1. cateringservices4656@gmail.com sent an email. Subject: "AC at HQ". They wrote: "I'm at the Bengaluru HQ today - the AC in F2-R1 is not working."
2. The desk opened TKT-2026-0001 (AC not working in F2-R1) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 6 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
4. It wrote to flexxftw12+facilities@gmail.com. Subject: "Work Order: AC not working in F2-R1 [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: AC not working in F2-R1 Repair. No asset rec…"
5. It wrote to cateringservices4656@gmail.com. Subject: "Re: AC at HQ [TKT-2026-0001]". The message starts: "Dear Ananya Rao, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-000…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: AC not working in F2-R1 (ACTIVE, HIGH, stage DISPATCHED, decision REPAIR_UNKNOWN)

Email received:

- From: cateringservices4656@gmail.com
- Subject: AC at HQ

```
I'm at the Bengaluru HQ today - the AC in F2-R1 is not working.
```

Reply sent:

- To: flexxftw12+facilities@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: AC not working in F2-R1 [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: AC not working in F2-R1

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 6

Requester: Ananya Rao <cateringservices4656@gmail.com>
Type: Air conditioning
Location: Bengaluru > Acme HQ Bengaluru
Team: Facilities & Maintenance
Priority: High (time-critical signal: "today")
Due by: 18 Oct, 7:50 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: Bengaluru HQ, F2-R1

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requ…
```

- To: cateringservices4656@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: AC at HQ [TKT-2026-0001]

```
Dear Ananya Rao,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

#### test_pune_approval_reaches_the_pune_admin_and_admin_can_approve — PASSED

What happened:

1. cateringservices4656@gmail.com sent an email. Subject: "Access card". They wrote: "I lost my access card, please issue a new one."
2. skcbsa1221@gmail.com sent an email. Subject: "Re: Ops Decision: Replacement access card [ITS-2026-0001]". They wrote: "approved"
3. The desk opened ITS-2026-0001 (Replacement access card) — handed to the team and still open.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: unknown. The rule says replace it after 3 repairs. No matching item was on file for that room, so warranty, AMC, and the repair count were left as unknown. Nothing was invented.
5. It wrote to skcbsa1221@gmail.com, skcbsa1221+pune@gmail.com. Subject: "Ops Decision: Replacement access card [ITS-2026-0001]". The message starts: "Dear Team, Your approval is requested. The particulars are below. Request: ITS-2026-0001 Subject: Replacement access card Needs your approval - access card req…"
6. It wrote to cateringservices4656@gmail.com. Subject: "Re: Access card [ITS-2026-0001]". The message starts: "Dear Ananya Rao, Your request has been logged and sent for approval. Request: ITS-2026-0001 Subject: Replacement access card You will be updated on this thread…"
7. It wrote to it.servicess8989+it@gmail.com. Subject: "Work Order: Replacement access card [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Replacement access card Repair. No asset rec…"
8. It wrote to cateringservices4656@gmail.com. Subject: "Access card [ITS-2026-0001]". The message starts: "Dear Ananya Rao, Request ITS-2026-0001 (Replacement access card) is approved and assigned to IT Support. You will be updated on this thread when the work is co…"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: Replacement access card (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR_UNKNOWN)

Email received:

- From: cateringservices4656@gmail.com
- Subject: Access card

```
I lost my access card, please issue a new one.
```

- From: skcbsa1221@gmail.com
- Subject: Re: Ops Decision: Replacement access card [ITS-2026-0001]

```
approved
```

Reply sent:

- To: skcbsa1221@gmail.com, skcbsa1221+pune@gmail.com
- From: workplace-desk@localhost
- Type: APPROVAL_REQUIRED
- Subject: Ops Decision: Replacement access card [ITS-2026-0001]

```
Dear Team,

Your approval is requested. The particulars are below.

Request: ITS-2026-0001
Subject: Replacement access card

Needs your approval - access card requests need admin sign-off

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Ananya Rao <cateringservices4656@gmail.com>
Type: Access card / ID
Location: Pune > Pune Hinjewadi
Team: IT Support

Details:
- Issue: lost access card

Reply "approve" or "reject, <reason>". You may also reply "tell requester: <message>".

Regards,
Workplace Team
```

- To: cateringservices4656@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Access card [ITS-2026-0001]

```
Dear Ananya Rao,

Your request has been logged and sent for approval.

Request: ITS-2026-0001
Subject: Replacement access card

You will be updated on this thread once a decision is recorded.

Regards,
Workplace Team
```

- To: it.servicess8989+it@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Replacement access card [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Replacement access card

Repair. No asset record matched this room at this branch, so warranty and repair count were not applied.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: unknown
- Replace after: 3

Requester: Ananya Rao <cateringservices4656@gmail.com>
Type: Access card / ID
Location: Pune > Pune Hinjewadi
Team: IT Support
Due by: 18 Oct, 7:50 AM

Details:
- Issue: lost access card

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <the card number issued or access granted>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detai…
```

- To: cateringservices4656@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Access card [ITS-2026-0001]

```
Dear Ananya Rao,

Request ITS-2026-0001 (Replacement access card) is approved and assigned to IT Support. You will be updated on this thread when the work is complete.
Once it's ready, you can collect it: IT desk, 2nd floor, Bengaluru HQ, 10 AM - 6 PM

Regards,
Workplace Team
```

#### test_outsider_gets_no_reply_no_case_no_work_order — PASSED

What happened:

1. anonymousxo1204@gmail.com sent an email. Subject: "fix fan". They wrote: "hey fix the fan in room 302"
2. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: anonymousxo1204@gmail.com
- Subject: fix fan

```
hey fix the fan in room 302
```

#### test_team_inbox_and_admin_are_not_treated_as_outsiders — PASSED

What happened:

1. kshitiz.vishwakarma2003@gmail.com sent an email. Subject: "VPN". They wrote: "VPN keeps dropping"
2. it.servicess8989+it@gmail.com sent an email. Subject: "Re: Work Order: VPN dropping [ITS-2026-0001]". They wrote: "on it, ETA 4 pm"
3. skcbsa1221@gmail.com sent an email. Subject: "pantry". They wrote: "Please get the pantry restocked on 3rd floor"
4. The desk opened ITS-2026-0001 (VPN dropping) — still open; TKT-2026-0001 (Restock pantry) — waiting for the sender to reply with missing details.
5. It checked the records. Nothing in the records blocked it, so the desk carried on.
6. It wrote to it.servicess8989+it@gmail.com. Subject: "Work Order: VPN dropping [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: VPN dropping New work order Requester: Kshit…"
7. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "Re: VPN [ITS-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, We have logged your request and assigned it to IT Support. Request: ITS-2026-0001 Subject: VPN dropping Status: Open You will be upda…"
8. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "VPN [ITS-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, Update on ITS-2026-0001 (VPN dropping) from IT Support: on it, ETA 4 pm Regards, Workplace Team"
9. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: VPN dropping [ITS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: ITS-2026-0001 Subject: VPN dropping IT Support update: on it, ETA 4 pm Requester: Kshitiz Vishwakarma <ks…"
10. It wrote to skcbsa1221@gmail.com. Subject: "Re: pantry [TKT-2026-0001]". The message starts: "Dear Skcbsa, Your request has been logged. Request: TKT-2026-0001 Subject: Restock pantry Please reply with the following: - Which office is this at (Acme HQ B…"
11. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- ITS-2026-0001: VPN dropping (ACTIVE, MEDIUM, stage IN_PROGRESS, decision PROCEED)
- TKT-2026-0001: Restock pantry (ACTIVE, MEDIUM, stage AWAITING_INFO)

Email received:

- From: kshitiz.vishwakarma2003@gmail.com
- Subject: VPN

```
VPN keeps dropping
```

- From: it.servicess8989+it@gmail.com
- Subject: Re: Work Order: VPN dropping [ITS-2026-0001]

```
on it, ETA 4 pm
```

- From: skcbsa1221@gmail.com
- Subject: pantry

```
Please get the pantry restocked on 3rd floor
```

Reply sent:

- To: it.servicess8989+it@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: VPN dropping [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: VPN dropping

New work order

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Network / Wi-Fi
Location: Mumbai > Mumbai BKC
Team: IT Support
Due by: 18 Oct, 7:50 AM

Details:
- Issue: VPN drops

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or priority is wrong, reply "change team to <team>", "change type to <type>", or "change …
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: VPN [ITS-2026-0001]

```
Dear Kshitiz Vishwakarma,

We have logged your request and assigned it to IT Support.

Request: ITS-2026-0001
Subject: VPN dropping
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: VPN [ITS-2026-0001]

```
Dear Kshitiz Vishwakarma,

Update on ITS-2026-0001 (VPN dropping) from IT Support: on it, ETA 4 pm

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: VPN dropping [ITS-2026-0001]

```
Dear Team,

Please note the following update.

Request: ITS-2026-0001
Subject: VPN dropping

IT Support update: on it, ETA 4 pm

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Network / Wi-Fi
Location: Mumbai > Mumbai BKC
Team: IT Support
Due by: 18 Oct, 7:50 AM

Details:
- Issue: VPN drops


Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: pantry [TKT-2026-0001]

```
Dear Skcbsa,

Your request has been logged.

Request: TKT-2026-0001
Subject: Restock pantry

Please reply with the following:
- Which office is this at (Acme HQ Bengaluru, Ahmedabad CG Road, Ahmedabad SG Highway, Bengaluru Electronic City, Bengaluru MG Road, Bengaluru Whitefield, Bhubaneswar Infocity, Bhubaneswar Jaydev Vihar, … (30 offices — reply with the branch name))?

Regards,
Workplace Team
```

#### test_unknown_office_is_asked_before_dispatch_then_routed_to_that_branch — PASSED

What happened:

1. rohan.mehta@acme.example sent an email. Subject: "fix fan". They wrote: "hey fix the fan in room 302"
2. rohan.mehta@acme.example sent an email. Subject: "Re: Re: fix fan [TKT-2026-0001]". They wrote: "Pune office"
3. The desk opened TKT-2026-0001 (Fix fan in room 302) — handed to the team and still open.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 8 repairs. The records did not call for a replacement, so this stayed a normal repair.
5. It wrote to rohan.mehta@acme.example. Subject: "Re: fix fan [TKT-2026-0001]". The message starts: "Dear Rohan Mehta, Your request has been logged. Request: TKT-2026-0001 Subject: Fix fan in room 302 Please reply with the following: - Which office is this at …"
6. It wrote to flexxftw12+pune@gmail.com. Subject: "Work Order: Fix fan in room 302 [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Fix fan in room 302 Repair This item. Repair…"
7. It wrote to rohan.mehta@acme.example. Subject: "Re: fix fan [TKT-2026-0001]". The message starts: "Dear Rohan Mehta, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Fix fan in room 302 (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: rohan.mehta@acme.example
- Subject: fix fan

```
hey fix the fan in room 302
```

- From: rohan.mehta@acme.example
- Subject: Re: Re: fix fan [TKT-2026-0001]

```
Pune office
```

Reply sent:

- To: rohan.mehta@acme.example
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: fix fan [TKT-2026-0001]

```
Dear Rohan Mehta,

Your request has been logged.

Request: TKT-2026-0001
Subject: Fix fan in room 302

Please reply with the following:
- Which office is this at (Acme HQ Bengaluru, Ahmedabad CG Road, Ahmedabad SG Highway, Bengaluru Electronic City, Bengaluru MG Road, Bengaluru Whitefield, Bhubaneswar Infocity, Bhubaneswar Jaydev Vihar, … (30 offices — reply with the branch name))?

Regards,
Workplace Team
```

- To: flexxftw12+pune@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Fix fan in room 302 [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Fix fan in room 302

Repair This item. Repairs on record: 0 of 8.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 8

Requester: Rohan Mehta <rohan.mehta@acme.example>
Type: Electrical
Location: Pune > Pune Hinjewadi
Team: Facilities - Pune
Due by: 18 Oct, 7:50 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities - Pune

Details:
- Location: room 302
- Issue: fan not working
- Office: Pune office

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works to…
```

- To: rohan.mehta@acme.example
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: fix fan [TKT-2026-0001]

```
Dear Rohan Mehta,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities - Pune.

Regards,
Workplace Team
```

#### test_office_is_asked_only_once — PASSED

What happened:

1. rohan.mehta@acme.example sent an email. Subject: "fix fan". They wrote: "hey fix the fan in room 302"
2. rohan.mehta@acme.example sent an email. Subject: "Re: Re: fix fan [TKT-2026-0001]". They wrote: "the main one"
3. The desk opened TKT-2026-0001 (Fix fan in room 302) — handed to the team and still open.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 8 repairs. The records did not call for a replacement, so this stayed a normal repair.
5. It wrote to rohan.mehta@acme.example. Subject: "Re: fix fan [TKT-2026-0001]". The message starts: "Dear Rohan Mehta, Your request has been logged. Request: TKT-2026-0001 Subject: Fix fan in room 302 Please reply with the following: - Which office is this at …"
6. It wrote to flexxftw12+facilities@gmail.com. Subject: "Work Order: Fix fan in room 302 [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Fix fan in room 302 Repair This item. Repair…"
7. It wrote to rohan.mehta@acme.example. Subject: "Re: fix fan [TKT-2026-0001]". The message starts: "Dear Rohan Mehta, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-00…"
8. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Fix fan in room 302 (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: rohan.mehta@acme.example
- Subject: fix fan

```
hey fix the fan in room 302
```

- From: rohan.mehta@acme.example
- Subject: Re: Re: fix fan [TKT-2026-0001]

```
the main one
```

Reply sent:

- To: rohan.mehta@acme.example
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: fix fan [TKT-2026-0001]

```
Dear Rohan Mehta,

Your request has been logged.

Request: TKT-2026-0001
Subject: Fix fan in room 302

Please reply with the following:
- Which office is this at (Acme HQ Bengaluru, Ahmedabad CG Road, Ahmedabad SG Highway, Bengaluru Electronic City, Bengaluru MG Road, Bengaluru Whitefield, Bhubaneswar Infocity, Bhubaneswar Jaydev Vihar, … (30 offices — reply with the branch name))?

Regards,
Workplace Team
```

- To: flexxftw12+facilities@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Fix fan in room 302 [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Fix fan in room 302

Repair This item. Repairs on record: 0 of 8.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 8

Requester: Rohan Mehta <rohan.mehta@acme.example>
Type: Electrical
Team: Facilities & Maintenance
Due by: 18 Oct, 7:51 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities & Maintenance

Details:
- Location: room 302
- Issue: fan not working
- Office: the main one

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to…
```

- To: rohan.mehta@acme.example
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: fix fan [TKT-2026-0001]

```
Dear Rohan Mehta,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities & Maintenance.

Regards,
Workplace Team
```

#### test_employee_and_office_free_requests_are_not_asked — PASSED

What happened:

1. cateringservices4656@gmail.com sent an email. Subject: "fix fan". They wrote: "hey fix the fan in room 302"
2. rohan.mehta@acme.example sent an email. Subject: "Figma". They wrote: "Please install Figma on my laptop."
3. The desk opened TKT-2026-0001 (Fix fan in room 302) — handed to the team and still open; ITS-2026-0001 (Install Figma) — handed to the team and still open.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 8 repairs. The records did not call for a replacement, so this stayed a normal repair.
5. It wrote to flexxftw12+pune@gmail.com. Subject: "Work Order: Fix fan in room 302 [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Fix fan in room 302 Repair This item. Repair…"
6. It wrote to cateringservices4656@gmail.com. Subject: "Re: fix fan [TKT-2026-0001]". The message starts: "Dear Ananya Rao, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-000…"
7. It wrote to it.servicess8989+it@gmail.com. Subject: "Work Order: Install Figma [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: Install Figma New work order Requester: Roha…"
8. It wrote to rohan.mehta@acme.example. Subject: "Re: Figma [ITS-2026-0001]". The message starts: "Dear Rohan Mehta, We have logged your request and assigned it to IT Support. Request: ITS-2026-0001 Subject: Install Figma Status: Open You will be updated on …"
9. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Fix fan in room 302 (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)
- ITS-2026-0001: Install Figma (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: cateringservices4656@gmail.com
- Subject: fix fan

```
hey fix the fan in room 302
```

- From: rohan.mehta@acme.example
- Subject: Figma

```
Please install Figma on my laptop.
```

Reply sent:

- To: flexxftw12+pune@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Fix fan in room 302 [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Fix fan in room 302

Repair This item. Repairs on record: 0 of 8.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 8

Requester: Ananya Rao <cateringservices4656@gmail.com>
Type: Electrical
Location: Pune > Pune Hinjewadi
Team: Facilities - Pune
Due by: 18 Oct, 7:51 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities - Pune

Details:
- Location: room 302
- Issue: fan not working

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to…
```

- To: cateringservices4656@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: fix fan [TKT-2026-0001]

```
Dear Ananya Rao,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities - Pune.

Regards,
Workplace Team
```

- To: it.servicess8989+it@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Install Figma [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: Install Figma

New work order

Requester: Rohan Mehta <rohan.mehta@acme.example>
Type: Software / licence
Team: IT Support
Due by: 18 Oct, 7:51 AM

Details:
- Software: Figma

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or priority is wrong, reply "change team to <team>", "change type to <type>", or "change priority to high".

Regards,
Workplace Team
```

- To: rohan.mehta@acme.example
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Figma [ITS-2026-0001]

```
Dear Rohan Mehta,

We have logged your request and assigned it to IT Support.

Request: ITS-2026-0001
Subject: Install Figma
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

#### test_work_order_subject_names_the_task — PASSED

What happened:

1. cateringservices4656@gmail.com sent an email. Subject: "fix fan". They wrote: "hey fix the fan in room 302"
2. The desk opened TKT-2026-0001 (Fix fan in room 302) — handed to the team and still open.
3. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 8 repairs. The records did not call for a replacement, so this stayed a normal repair.
4. It wrote to flexxftw12+pune@gmail.com. Subject: "Work Order: Fix fan in room 302 [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Fix fan in room 302 Repair This item. Repair…"
5. It wrote to cateringservices4656@gmail.com. Subject: "Re: fix fan [TKT-2026-0001]". The message starts: "Dear Ananya Rao, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-000…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Fix fan in room 302 (ACTIVE, MEDIUM, stage DISPATCHED, decision REPAIR)

Email received:

- From: cateringservices4656@gmail.com
- Subject: fix fan

```
hey fix the fan in room 302
```

Reply sent:

- To: flexxftw12+pune@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Fix fan in room 302 [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Fix fan in room 302

Repair This item. Repairs on record: 0 of 8.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 8

Requester: Ananya Rao <cateringservices4656@gmail.com>
Type: Electrical
Location: Pune > Pune Hinjewadi
Team: Facilities - Pune
Due by: 18 Oct, 7:51 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities - Pune

Details:
- Location: room 302
- Issue: fan not working

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was fixed or done (a photo works too)>"
- "assign to…
```

- To: cateringservices4656@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: fix fan [TKT-2026-0001]

```
Dear Ananya Rao,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities - Pune.

Regards,
Workplace Team
```

#### test_each_request_from_one_mail_gets_its_own_update_subject — PASSED

What happened:

1. kshitiz.vishwakarma2003@gmail.com sent an email. Subject: "two things". They wrote: "1. Fan in room 302 is not working 2. VPN keeps dropping"
2. flexxftw12@gmail.com sent an email. Subject: "Re: Work Order: Fix fan in room 302 [TKT-2026-0001]". They wrote: "done, fan replaced"
3. The desk opened TKT-2026-0001 (Fix fan in room 302) — closed as done; ITS-2026-0001 (VPN dropping) — handed to the team and still open.
4. It checked the records. It did not find that item in the office records. Warranty: unknown. No AMC (service contract) was on file. Repairs already on record: 0. The rule says replace it after 8 repairs. The records did not call for a replacement, so this stayed a normal repair.
5. It wrote to flexxftw12+west@gmail.com. Subject: "Work Order: Fix fan in room 302 [TKT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: TKT-2026-0001 Subject: Fix fan in room 302 Repair This item. Repair…"
6. It wrote to it.servicess8989+it@gmail.com. Subject: "Work Order: VPN dropping [ITS-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: ITS-2026-0001 Subject: VPN dropping New work order Tasks assigned: …"
7. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "Re: two things [TKT-2026-0001] [ITS-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT…"
8. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "Fix fan in room 302 [TKT-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, Good news - TKT-2026-0001 (Fix fan in room 302) has been taken care of. Note from Facilities - West: Fan replaced If anything is stil…"
9. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: Fix fan in room 302 [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Fix fan in room 302 Completed by Facilities - West: Fan replaced Record check: - I…"
10. It wrote to flexxftw12@gmail.com. Subject: "Proof Needed: Fix fan in room 302 [TKT-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: TKT-2026-0001 Subject: Fix fan in room 302 Thanks for completing this. To close it as verified, please re…"
11. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- TKT-2026-0001: Fix fan in room 302 (RESOLVED, MEDIUM, stage RESOLVED, decision REPAIR)
- ITS-2026-0001: VPN dropping (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: kshitiz.vishwakarma2003@gmail.com
- Subject: two things

```
1. Fan in room 302 is not working
2. VPN keeps dropping
```

- From: flexxftw12@gmail.com
- Subject: Re: Work Order: Fix fan in room 302 [TKT-2026-0001]

```
done, fan replaced
```

Reply sent:

- To: flexxftw12+west@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Fix fan in room 302 [TKT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: TKT-2026-0001
Subject: Fix fan in room 302

Repair This item. Repairs on record: 0 of 8.

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 8

Tasks assigned:
1. Fan in room 302 is not working
2. VPN keeps dropping

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Electrical
Location: Mumbai > Mumbai BKC
Team: Facilities - West
Due by: 18 Oct, 7:51 AM
Preferred vendor: CleanSupply Partners

Investigation:
Approved vendor on file: CleanSupply Partners; Route to Facilities - West

Details:
- Location: room 302
- Issue: fan not working

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work …
```

- To: it.servicess8989+it@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: VPN dropping [ITS-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: ITS-2026-0001
Subject: VPN dropping

New work order

Tasks assigned:
1. Fan in room 302 is not working
2. VPN keeps dropping

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Network / Wi-Fi
Location: Mumbai > Mumbai BKC
Team: IT Support
Due by: 18 Oct, 7:51 AM

Details:
- Issue: VPN drops

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <what was done and the asset tag / ticket number if any>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or priority is w…
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: two things [TKT-2026-0001] [ITS-2026-0001]

```
Dear Kshitiz Vishwakarma,

Your request has been logged with the facilities team and marked for priority handling. You will be updated on this thread. (Ref: TKT-2026-0001)
Assigned it to Facilities - West.

We have logged your request and assigned it to IT Support.

Request: ITS-2026-0001
Subject: VPN dropping
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Fix fan in room 302 [TKT-2026-0001]

```
Dear Kshitiz Vishwakarma,

Good news - TKT-2026-0001 (Fix fan in room 302) has been taken care of.
Note from Facilities - West: Fan replaced

If anything is still not right, just reply "not fixed" and I'll reopen it. Otherwise it closes automatically in 3 days.

Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Fix fan in room 302 [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Fix fan in room 302

Completed by Facilities - West: Fan replaced

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 8

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Electrical
Location: Mumbai > Mumbai BKC
Team: Facilities - West
Due by: 18 Oct, 7:51 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: room 302
- Issue: fan not working


Regards,
Workplace Team
```

- To: flexxftw12@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Proof Needed: Fix fan in room 302 [TKT-2026-0001]

```
Dear Team,

Please note the following update.

Request: TKT-2026-0001
Subject: Fix fan in room 302

Thanks for completing this. To close it as verified, please reply with what was fixed or done (a photo works too) (or attach a photo).

Record check:
- Item: no matching asset on record at this branch
- Warranty: unknown
- AMC: none on record
- Repairs on record: 0
- Replace after: 8

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Electrical
Location: Mumbai > Mumbai BKC
Team: Facilities - West
Due by: 18 Oct, 7:51 AM
Preferred vendor: CleanSupply Partners

Details:
- Location: room 302
- Issue: fan not working


Regards,
Workplace Team
```

#### test_new_request_in_an_old_thread_drops_the_old_ticket_numbers — PASSED

What happened:

1. kshitiz.vishwakarma2003@gmail.com sent an email. Subject: "Re: stationery request [SUP-2026-0001] [PRK-2026-0001]". They wrote: "I need a seat from 10th Oct"
2. The desk opened SEAT-2026-0001 (Seat allocation from 10th Oct) — handed to the team and still open.
3. It checked the records. Nothing in the records blocked it, so the desk carried on.
4. It wrote to skcbsa1221@gmail.com. Subject: "Work Order: Seat allocation from 10th Oct [SEAT-2026-0001]". The message starts: "Dear Team, A work order has been assigned to your team. The particulars are below. Request: SEAT-2026-0001 Subject: Seat allocation from 10th Oct New work orde…"
5. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "Re: Seat allocation from 10th Oct [SEAT-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, We have logged your request and assigned it to Admin & Workplace. Request: SEAT-2026-0001 Subject: Seat allocation from 10th Oct Stat…"
6. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- SEAT-2026-0001: Seat allocation from 10th Oct (ACTIVE, MEDIUM, stage DISPATCHED, decision PROCEED)

Email received:

- From: kshitiz.vishwakarma2003@gmail.com
- Subject: Re: stationery request [SUP-2026-0001] [PRK-2026-0001]

```
I need a seat from 10th Oct
```

Reply sent:

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: ACTION_REQUIRED
- Subject: Work Order: Seat allocation from 10th Oct [SEAT-2026-0001]

```
Dear Team,

A work order has been assigned to your team. The particulars are below.

Request: SEAT-2026-0001
Subject: Seat allocation from 10th Oct

New work order

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Seating / desk move
Location: Mumbai > Mumbai BKC
Team: Admin & Workplace
Due by: 18 Oct, 11:51 PM

Details:
- Employee name: Kshitiz Vishwakarma
- Date: 2026-10-10

Please reply to this email with one of the following:
- "on it" or "ETA 4 pm" to update the requester
- "issue: <what is blocking>" if the work cannot proceed
- "done - <the seat number allotted>"
- "assign to <email>" to transfer the work order
- "tell requester: <message>", "change <detail> to <value>", "close", or "cancel"
The request is marked verified only when that note, or a photograph, is attached to your reply.
If the team, type, or priority is wrong, reply "change team to <team>",…
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Seat allocation from 10th Oct [SEAT-2026-0001]

```
Dear Kshitiz Vishwakarma,

We have logged your request and assigned it to Admin & Workplace.

Request: SEAT-2026-0001
Subject: Seat allocation from 10th Oct
Status: Open

You will be updated on this thread when the work is complete.

Regards,
Workplace Team
```

#### test_empty_template_in_old_thread_does_not_invent_tickets — PASSED

What happened:

1. kshitiz.vishwakarma2003@gmail.com sent an email. Subject: "Re: stationery request [SUP-2099-0001] [PRK-2099-0001]". They wrote: "Please find the details for my requests: - Car parking (PRK-2099-0001): - Visiting car (VIS-2099-0001): [VISITOR NAME, COMPANY, DATE AND TIME] - Desk allocatio…"
2. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "Re: stationery request". The message starts: "Dear Kshitiz Vishwakarma, Those request numbers are no longer open, so no new request has been raised from that message. Please send a new email for any item t…"
3. Result: this test passed. The message above is the reply the system itself wrote.


Email received:

- From: kshitiz.vishwakarma2003@gmail.com
- Subject: Re: stationery request [SUP-2099-0001] [PRK-2099-0001]

```
Please find the details for my requests:

- Car parking (PRK-2099-0001):
- Visiting car (VIS-2099-0001): [VISITOR NAME, COMPANY, DATE AND TIME]
- Desk allocation (SEAT-2099-0001): [START DATE]
```

Reply sent:

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: stationery request

```
Dear Kshitiz Vishwakarma,

Those request numbers are no longer open, so no new request has been raised from that message. Please send a new email for any item that still requires action.

Regards,
Workplace Team
```

#### test_vague_cancel_closes_every_waiting_ask — PASSED

What happened:

1. kshitiz.vishwakarma2003@gmail.com sent an email. Subject: "two asks". They wrote: "Need parking and a visitor pass tomorrow"
2. kshitiz.vishwakarma2003@gmail.com sent an email. Subject: "Re: Re: two asks [PRK-2026-0001] [VIS-2026-0001]". They wrote: "I don't want, thanks"
3. The desk opened PRK-2026-0001 (Car parking) — cancelled; VIS-2026-0001 (Visitor pass) — cancelled.
4. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "Re: two asks [PRK-2026-0001] [VIS-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, Your request has been logged. Request: PRK-2026-0001 Subject: Car parking Please reply with the following: - What is the vehicle numb…"
5. It wrote to skcbsa1221+security@gmail.com. Subject: "Done: Visitor pass [VIS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: VIS-2026-0001 Subject: Visitor pass Cancelled by requester - no action needed Requester: Kshitiz Vishwaka…"
6. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: Visitor pass [VIS-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: VIS-2026-0001 Subject: Visitor pass Completed by the desk - Cancelled by requester - no action needed Req…"
7. It wrote to skcbsa1221+security@gmail.com. Subject: "Done: Car parking [PRK-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: PRK-2026-0001 Subject: Car parking Cancelled by requester - no action needed Requester: Kshitiz Vishwakar…"
8. It wrote to skcbsa1221@gmail.com. Subject: "Ops Update: Car parking [PRK-2026-0001]". The message starts: "Dear Team, Please note the following update. Request: PRK-2026-0001 Subject: Car parking Completed by the desk - Cancelled by requester - no action needed Requ…"
9. It wrote to kshitiz.vishwakarma2003@gmail.com. Subject: "Re: two asks [PRK-2026-0001]". The message starts: "Dear Kshitiz Vishwakarma, Request PRK-2026-0001 has been cancelled. Regards, Workplace Team"
10. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- PRK-2026-0001: Car parking (CANCELLED, MEDIUM, stage CANCELLED)
- VIS-2026-0001: Visitor pass (CANCELLED, MEDIUM, stage CANCELLED)

Email received:

- From: kshitiz.vishwakarma2003@gmail.com
- Subject: two asks

```
Need parking and a visitor pass tomorrow
```

- From: kshitiz.vishwakarma2003@gmail.com
- Subject: Re: Re: two asks [PRK-2026-0001] [VIS-2026-0001]

```
I don't want, thanks
```

Reply sent:

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: two asks [PRK-2026-0001] [VIS-2026-0001]

```
Dear Kshitiz Vishwakarma,

Your request has been logged.

Request: PRK-2026-0001
Subject: Car parking

Please reply with the following:
- What is the vehicle number?
- Which date do you need parking?

Your request has been logged.

Request: VIS-2026-0001
Subject: Visitor pass

Please reply with the following:
- Who is visiting (name and company)?
- Which date and time is the visit?

Regards,
Workplace Team
```

- To: skcbsa1221+security@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Done: Visitor pass [VIS-2026-0001]

```
Dear Team,

Please note the following update.

Request: VIS-2026-0001
Subject: Visitor pass

Cancelled by requester - no action needed

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Visitor pre-registration
Location: Mumbai > Mumbai BKC
Team: Security & Front Desk


Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Visitor pass [VIS-2026-0001]

```
Dear Team,

Please note the following update.

Request: VIS-2026-0001
Subject: Visitor pass

Completed by the desk - Cancelled by requester - no action needed

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Visitor pre-registration
Location: Mumbai > Mumbai BKC
Team: Security & Front Desk


Regards,
Workplace Team
```

- To: skcbsa1221+security@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Done: Car parking [PRK-2026-0001]

```
Dear Team,

Please note the following update.

Request: PRK-2026-0001
Subject: Car parking

Cancelled by requester - no action needed

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Parking
Location: Mumbai > Mumbai BKC
Team: Security & Front Desk


Regards,
Workplace Team
```

- To: skcbsa1221@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Ops Update: Car parking [PRK-2026-0001]

```
Dear Team,

Please note the following update.

Request: PRK-2026-0001
Subject: Car parking

Completed by the desk - Cancelled by requester - no action needed

Requester: Kshitiz Vishwakarma <kshitiz.vishwakarma2003@gmail.com>
Type: Parking
Location: Mumbai > Mumbai BKC
Team: Security & Front Desk


Regards,
Workplace Team
```

- To: kshitiz.vishwakarma2003@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: two asks [PRK-2026-0001]

```
Dear Kshitiz Vishwakarma,

Request PRK-2026-0001 has been cancelled.

Regards,
Workplace Team
```

#### test_catering_asks_for_time_before_approval — PASSED

What happened:

1. cateringservices4656@gmail.com sent an email. Subject: "Lunch". They wrote: "Lunch for 10 people from outside tomorrow"
2. The desk opened CAT-2026-0001 (Lunch for 10) — waiting for the sender to reply with missing details.
3. It wrote to cateringservices4656@gmail.com. Subject: "Re: Lunch [CAT-2026-0001]". The message starts: "Dear Ananya Rao, Your request has been logged. Request: CAT-2026-0001 Subject: Lunch for 10 Please reply with the following: - What time should it be ready? Re…"
4. Result: this test passed. The message above is the reply the system itself wrote.


Case state:

- CAT-2026-0001: Lunch for 10 (ACTIVE, MEDIUM, stage AWAITING_INFO)

Email received:

- From: cateringservices4656@gmail.com
- Subject: Lunch

```
Lunch for 10 people from outside tomorrow
```

Reply sent:

- To: cateringservices4656@gmail.com
- From: workplace-desk@localhost
- Type: INFORMATION_ONLY
- Subject: Re: Lunch [CAT-2026-0001]

```
Dear Ananya Rao,

Your request has been logged.

Request: CAT-2026-0001
Subject: Lunch for 10

Please reply with the following:
- What time should it be ready?

Regards,
Workplace Team
```

#### test_question_about_a_branch_is_answered_from_knowledge — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_v3_foundation.py

16 cases, 0 failed.

#### test_legal_entity_and_person_link — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_job_processed_with_job_tenant_not_first_tenant — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Regression: worker must use job.tenant_id, not first Tenant row.

No email was stored for this case.

#### test_outbox_enqueue_and_flush — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_approval_engine_policy_and_fallback — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_sla_and_budget_engines — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_evidence_engine_blocks_unverified — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- CASE-EVD-1: AC repair (IN_PROGRESS, MEDIUM)

No email was stored for this case.

#### test_context_gateway_marks_unavailable — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_asset_and_incident_and_erp_stub — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_ai_governance_emergency_and_confidence — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_matching_engine_po_invoice — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_admin_modules_mail_lifecycle_utility — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_outcome_spine_helpers — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- CASE-SPINE-1: Spine (IN_PROGRESS, HIGH)
- CASE-SPINE-DESK: AC (ACTIVE, MEDIUM)

No email was stored for this case.

#### test_sourcing_rfq_award — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_pm_sweeper_creates_outcome — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

Case state:

- PM-2026-0001: PM due: Filter change (ACTIVE, MEDIUM, stage DISPATCHED)

No email was stored for this case.

#### test_workplace_seat_and_p2p_pr — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_sod_helpers — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

### test_vendor_lifecycle.py

5 cases, 0 failed.

#### test_invite_register_score_activate_flow — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_expired_token_rejected — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_suspended_excluded_from_desk_tools — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_scorecard_ledger_backed — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

#### test_invite_activate_suspend_ledger_events — PASSED

What happened:

No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.


No email was sent in this test. It only checked one rule inside the system, with no mailbox involved. The check passed.

No email was stored for this case.

