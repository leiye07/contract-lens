"""Authored fictional sources. No client contracts, laws or private evaluation answers in model context."""

import hashlib, json
from psycopg.types.json import Jsonb
from .db import connect

QUESTION = "Can the customer terminate early, and what payments or obligations remain?"
CHECKLIST = ["termination", "notice", "payment", "survival", "amendments"]
DOCUMENTS = [
    {
        "id": "msa",
        "title": "Fictional software services agreement",
        "version": "2026-01",
        "clauses": [
            (
                "MSA-1",
                "1",
                "Agreement and definitions",
                "This fictional Agreement consists of this master services agreement, Order Form 1, the Data Processing Addendum, Schedule A and signed amendments. Customer means Acorn Demo Ltd. Provider means Cedar Demo Systems. Monthly Subscription Fee has the meaning stated in Order Form 1.",
                [("ORDER-1", "definition"), ("SCHEDULE-A-1", "incorporation")],
            ),
            (
                "MSA-2",
                "2",
                "Termination for convenience",
                "Customer may terminate this Agreement for convenience on sixty days' written notice to Provider. The notice requirements in Section 5 apply. Accrued payments, any fee under Schedule A and surviving obligations in Section 4 remain applicable.",
                [
                    ("MSA-5", "cross_reference"),
                    ("MSA-3", "cross_reference"),
                    ("SCHEDULE-A-1", "cross_reference"),
                    ("MSA-4", "cross_reference"),
                ],
            ),
            (
                "MSA-3",
                "3",
                "Payments at termination",
                "Customer shall pay undisputed fees accrued through the effective termination date. Future subscription fees are not accelerated except for an early termination fee expressly specified in Schedule A. This clause does not state the amount of that fee.",
                [("SCHEDULE-A-1", "cross_reference"), ("ORDER-1", "definition")],
            ),
            (
                "MSA-4",
                "4",
                "Surviving obligations",
                "Accrued payment obligations and confidentiality obligations survive termination. The export and deletion process in DPA Section 2 also applies after termination.",
                [("DPA-2", "cross_reference")],
            ),
            (
                "MSA-5",
                "5",
                "Written notice",
                "Termination notices must be sent in writing to the contractual notice contacts. Email receipt is effective on the next business day after acknowledged delivery. This fictional package does not provide the contacts or a business-day calendar.",
                [],
            ),
            (
                "MSA-6",
                "6",
                "Document changes",
                "A signed amendment may expressly replace a section of this master services agreement. This Agreement does not specify an order of priority between amendments with the same effective date.",
                [],
            ),
        ],
    },
    {
        "id": "order",
        "title": "Fictional Order Form 1",
        "version": "2026-01",
        "clauses": [
            (
                "ORDER-1",
                "1",
                "Term and subscription fee",
                "The subscription term is twelve months. The Monthly Subscription Fee is USD 1,000. Termination rights and any early termination fee are governed by the Agreement and Schedule A.",
                [("MSA-2", "cross_reference"), ("SCHEDULE-A-1", "cross_reference")],
            )
        ],
    },
    {
        "id": "dpa",
        "title": "Fictional Data Processing Addendum",
        "version": "2026-01",
        "clauses": [
            (
                "DPA-2",
                "2",
                "Data export and deletion",
                "For thirty days after termination, Provider will make Customer data available for export. Provider will then delete remaining Customer data except records required to be retained by applicable law. This clause does not identify any particular legal retention requirement.",
                [],
            )
        ],
    },
    {
        "id": "schedule-a",
        "title": "Fictional Schedule A — early termination fee",
        "version": "2026-01",
        "clauses": [
            (
                "SCHEDULE-A-1",
                "1",
                "Convenience termination fee",
                "For Customer termination for convenience, the early termination fee is two times the Monthly Subscription Fee in Order Form 1, in addition to undisputed accrued fees. This fee does not apply to termination for Provider's uncured material breach.",
                [("ORDER-1", "definition")],
            )
        ],
    },
    {
        "id": "amendment-1",
        "title": "Fictional Amendment 1",
        "version": "2026-02-01",
        "clauses": [
            (
                "AMENDMENT-1",
                "1",
                "Revised termination notice",
                "Effective 1 February 2026, the parties replace the sixty-day convenience termination notice period in MSA Section 2 with thirty days. All other terms of MSA Section 2 remain unchanged.",
                [("MSA-2", "amends")],
            )
        ],
    },
]
AMENDMENT2 = {
    "id": "amendment-2",
    "title": "Fictional Amendment 2",
    "version": "2026-02-01",
    "clauses": [
        (
            "AMENDMENT-2",
            "1",
            "Alternative termination notice",
            "Effective 1 February 2026, the parties replace the sixty-day convenience termination notice period in MSA Section 2 with forty-five days. This amendment does not refer to Amendment 1 and does not state an order of priority.",
            [("MSA-2", "amends")],
        )
    ],
}
SCENARIOS = {
    "termination-complete": {
        "package_id": "fictional-complete-v1",
        "name": "Complete contract package",
    },
    "termination-missing-schedule": {
        "package_id": "fictional-missing-schedule-v1",
        "name": "Missing fee schedule",
    },
    "termination-conflicting-amendments": {
        "package_id": "fictional-conflicts-v1",
        "name": "Conflicting amendments",
    },
}


def materialize(sid):
    import copy

    docs = copy.deepcopy(DOCUMENTS)
    if sid == "termination-conflicting-amendments":
        docs.append(copy.deepcopy(AMENDMENT2))
    for doc in docs:
        doc["available"] = not (
            sid == "termination-missing-schedule" and doc["id"] == "schedule-a"
        )
        clauses = []
        body = ""
        for cid, section, title, text, links in doc.pop("clauses"):
            if not doc["available"]:
                continue
            prefix = f"Section {section}: {title}\n"
            body += prefix
            start = len(body)
            body += text
            clauses.append(
                {
                    "id": cid,
                    "section": section,
                    "title": title,
                    "text": text,
                    "char_start": start,
                    "char_end": len(body),
                    "links": links,
                }
            )
            body += "\n\n"
        doc.update(
            body=body, sha256=hashlib.sha256(body.encode()).hexdigest(), clauses=clauses
        )
    manifest = {
        "id": SCENARIOS[sid]["package_id"],
        "name": SCENARIOS[sid]["name"],
        "fictional": True,
        "documents": docs,
    }
    sha = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return manifest, sha


def seed():
    with connect() as c:
        c.execute("SELECT pg_advisory_xact_lock(553301)")
        for sid, scenario in SCENARIOS.items():
            manifest, sha = materialize(sid)
            pid = manifest["id"]
            old = c.execute(
                "SELECT sha256 FROM packages WHERE id=%s", (pid,)
            ).fetchone()
            if old:
                if old["sha256"] != sha:
                    raise RuntimeError(
                        "Immutable package hash changed; create a new package version"
                    )
                continue
            c.execute(
                "INSERT INTO packages VALUES (%s,%s,%s)", (pid, sha, manifest["name"])
            )
            allids = []
            for doc in manifest["documents"]:
                c.execute(
                    "INSERT INTO documents VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (
                        pid,
                        doc["id"],
                        doc["title"],
                        doc["version"],
                        doc["available"],
                        doc["body"],
                        doc["sha256"],
                    ),
                )
                for clause in doc["clauses"]:
                    allids.append(clause["id"])
                    c.execute(
                        "INSERT INTO clauses(package_id,id,document_id,section,title,body,char_start,char_end) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            pid,
                            clause["id"],
                            doc["id"],
                            clause["section"],
                            clause["title"],
                            clause["text"],
                            clause["char_start"],
                            clause["char_end"],
                        ),
                    )
                    for target, kind in clause["links"]:
                        c.execute(
                            "INSERT INTO clause_links VALUES (%s,%s,%s,%s)",
                            (pid, clause["id"], target, kind),
                        )
            reference = [
                x
                for x in allids
                if x
                in {
                    "MSA-2",
                    "MSA-3",
                    "MSA-4",
                    "MSA-5",
                    "MSA-6",
                    "ORDER-1",
                    "DPA-2",
                    "SCHEDULE-A-1",
                    "AMENDMENT-1",
                    "AMENDMENT-2",
                }
            ]
            c.execute(
                "INSERT INTO scenarios VALUES (%s,%s,%s,%s,%s,%s)",
                (sid, pid, QUESTION, Jsonb(CHECKLIST), "1", Jsonb(reference)),
            )


def package(pid):
    with connect() as c:
        p = c.execute(
            "SELECT id,sha256,name FROM packages WHERE id=%s", (pid,)
        ).fetchone()
        if not p:
            raise ValueError("Unknown package")
        docs = c.execute(
            "SELECT id,title,version,available,sha256 FROM documents WHERE package_id=%s ORDER BY id",
            (pid,),
        ).fetchall()
        return {**p, "fictional": True, "documents": docs}


def read(pid, cid):
    with connect() as c:
        row = c.execute(
            "SELECT c.id,c.document_id,c.section,c.title,c.body text,c.char_start,c.char_end,d.title document_title,d.version document_version,d.sha256 document_sha256 FROM clauses c JOIN documents d ON c.package_id=d.package_id AND c.document_id=d.id WHERE c.package_id=%s AND c.id=%s",
            (pid, cid),
        ).fetchone()
        if not row:
            raise ValueError("Clause unavailable in this package")
        links = c.execute(
            "SELECT l.target_id,l.kind,(c.id IS NOT NULL) available FROM clause_links l LEFT JOIN clauses c ON c.package_id=l.package_id AND c.id=l.target_id WHERE l.package_id=%s AND l.source_id=%s ORDER BY target_id",
            (pid, cid),
        ).fetchall()
        return {**row, "references": links}


def search(pid, query, limit=4):
    with connect() as c:
        rows = c.execute(
            "SELECT id,document_id,section,title,ts_rank(search_vector,websearch_to_tsquery('english',%s)) rank FROM clauses WHERE package_id=%s AND search_vector @@ websearch_to_tsquery('english',%s) ORDER BY rank DESC,id LIMIT %s",
            (query, pid, query, limit),
        ).fetchall()
        if not rows:
            rows = c.execute(
                "SELECT id,document_id,section,title FROM clauses WHERE package_id=%s AND (title ILIKE %s OR body ILIKE %s) ORDER BY id LIMIT %s",
                (pid, "%" + query + "%", "%" + query + "%", limit),
            ).fetchall()
        return {
            "matches": rows,
            "strategy": "postgresql_lexical",
            "note": "Search returns pointers, not proof of absence. Read clauses before citing.",
        }
