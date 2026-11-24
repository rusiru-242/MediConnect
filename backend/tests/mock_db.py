"""In-memory mock MongoDB database for lightning-fast, offline testing without Atlas network dependencies."""

import copy
from datetime import datetime
import re
from typing import Any, Dict, List, Optional
from bson import ObjectId


def _get_nested(doc: Dict[str, Any], path: str) -> Any:
    parts = path.split(".")
    curr = doc
    for i, p in enumerate(parts):
        if isinstance(curr, dict) and p in curr:
            curr = curr[p]
        elif isinstance(curr, list):
            rem = ".".join(parts[i:])
            for item in curr:
                if isinstance(item, dict):
                    v = _get_nested(item, rem)
                    if v is not None:
                        return v
            return None
        else:
            return None
    return curr


def _set_nested(doc: Dict[str, Any], path: str, value: Any) -> None:
    if ".$. " in path or ".$. " in path.replace(" ", "") or ".$. " in path or ".$. " in path:
        pass
    parts = path.split(".")
    curr = doc
    for p in parts[:-1]:
        if p not in curr or not isinstance(curr[p], dict):
            curr[p] = {}
        curr = curr[p]
    curr[parts[-1]] = copy.deepcopy(value)


def _push_nested(doc: Dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    curr = doc
    for p in parts[:-1]:
        if p not in curr or not isinstance(curr[p], dict):
            curr[p] = {}
        curr = curr[p]
    if parts[-1] not in curr or not isinstance(curr[parts[-1]], list):
        curr[parts[-1]] = []
    curr[parts[-1]].append(copy.deepcopy(value))


def _match_val(actual: Any, expected: Any) -> bool:
    if isinstance(expected, dict):
        for op, op_val in expected.items():
            if op == "$in":
                matched = False
                for item in op_val:
                    if actual == item or str(actual) == str(item):
                        matched = True
                        break
                if not matched:
                    return False
            elif op == "$nin":
                for item in op_val:
                    if actual == item or str(actual) == str(item):
                        return False
            elif op == "$gte":
                if actual is None or actual < op_val:
                    return False
            elif op == "$lte":
                if actual is None or actual > op_val:
                    return False
            elif op == "$gt":
                if actual is None or actual <= op_val:
                    return False
            elif op == "$lt":
                if actual is None or actual >= op_val:
                    return False
            elif op == "$ne":
                if actual == op_val or str(actual) == str(op_val):
                    return False
            elif op == "$regex":
                pat = op_val
                flags = 0
                if expected.get("$options") == "i":
                    flags = re.IGNORECASE
                if not isinstance(actual, str) or not re.search(pat, actual, flags):
                    return False
            elif op == "$exists":
                exists = actual is not None
                if exists != bool(op_val):
                    return False
        return True
    elif hasattr(expected, "pattern"):
        return isinstance(actual, str) and bool(expected.search(actual))
    else:
        if actual == expected:
            return True
        if isinstance(actual, ObjectId) or isinstance(expected, ObjectId):
            return str(actual) == str(expected)
        return False


def match_doc(doc: Dict[str, Any], query: Optional[Dict[str, Any]]) -> bool:
    if not query:
        return True
    for k, v in query.items():
        if k == "$or":
            if not any(match_doc(doc, sub) for sub in v):
                return False
            continue
        if k == "$and":
            if not all(match_doc(doc, sub) for sub in v):
                return False
            continue
        actual = _get_nested(doc, k)
        if not _match_val(actual, v):
            return False
    return True


class MockCursor:
    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = docs

    def sort(self, key_or_list, direction=1):
        if isinstance(key_or_list, list):
            for k, d in reversed(key_or_list):
                rev = (d == -1)
                self._docs.sort(key=lambda doc: str(_get_nested(doc, k) or ""), reverse=rev)
        else:
            rev = (direction == -1)
            self._docs.sort(key=lambda doc: str(_get_nested(doc, key_or_list) or ""), reverse=rev)
        return self

    def limit(self, n: int):
        self._docs = self._docs[:n]
        return self

    def skip(self, n: int):
        self._docs = self._docs[n:]
        return self

    def __iter__(self):
        return iter(self._docs)

    def __getitem__(self, item):
        return self._docs[item]

    def count(self):
        return len(self._docs)


class InsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class InsertManyResult:
    def __init__(self, inserted_ids):
        self.inserted_ids = inserted_ids


class UpdateResult:
    def __init__(self, matched_count, modified_count):
        self.matched_count = matched_count
        self.modified_count = modified_count


class DeleteResult:
    def __init__(self, deleted_count):
        self.deleted_count = deleted_count


class MockCollection:
    def __init__(self, name: str):
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    def insert_one(self, doc: Dict[str, Any]):
        d = copy.deepcopy(doc)
        if "_id" not in d:
            d["_id"] = ObjectId()
        self.docs.append(d)
        return InsertOneResult(d["_id"])

    def insert_many(self, docs: List[Dict[str, Any]]):
        ids = []
        for doc in docs:
            res = self.insert_one(doc)
            ids.append(res.inserted_id)
        return InsertManyResult(ids)

    def find_one(self, query: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None):
        for d in self.docs:
            if match_doc(d, query):
                res = copy.deepcopy(d)
                return self._apply_projection(res, projection)
        return None

    def find(self, query: Optional[Dict[str, Any]] = None, projection: Optional[Dict[str, Any]] = None):
        res = []
        for d in self.docs:
            if match_doc(d, query):
                res.append(self._apply_projection(copy.deepcopy(d), projection))
        return MockCursor(res)

    def count_documents(self, query: Optional[Dict[str, Any]] = None):
        return sum(1 for d in self.docs if match_doc(d, query))

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        for d in self.docs:
            if match_doc(d, query):
                self._apply_update(d, update)
                return UpdateResult(1, 1)
        if upsert:
            new_doc = copy.deepcopy(query)
            self._apply_update(new_doc, update)
            self.insert_one(new_doc)
            return UpdateResult(0, 1)
        return UpdateResult(0, 0)

    def update_many(self, query: Dict[str, Any], update: Dict[str, Any]):
        cnt = 0
        for d in self.docs:
            if match_doc(d, query):
                self._apply_update(d, update)
                cnt += 1
        return UpdateResult(cnt, cnt)

    def delete_one(self, query: Dict[str, Any]):
        for i, d in enumerate(self.docs):
            if match_doc(d, query):
                self.docs.pop(i)
                return DeleteResult(1)
        return DeleteResult(0)

    def delete_many(self, query: Optional[Dict[str, Any]] = None):
        before = len(self.docs)
        self.docs = [d for d in self.docs if not match_doc(d, query)]
        return DeleteResult(before - len(self.docs))

    def create_index(self, *args, **kwargs):
        return "idx_ok"

    def create_indexes(self, *args, **kwargs):
        return ["idx_ok"]

    def list_indexes(self):
        return []

    def drop_indexes(self):
        pass

    def _apply_projection(self, doc: Dict[str, Any], projection: Optional[Dict[str, Any]]):
        if not projection:
            return doc
        includes = {k: v for k, v in projection.items() if k != "_id" and v == 1}
        excludes = {k: v for k, v in projection.items() if v == 0}
        if includes:
            filtered = {}
            if projection.get("_id", 1) != 0 and "_id" in doc:
                filtered["_id"] = doc["_id"]
            for k in includes:
                if k in doc:
                    filtered[k] = doc[k]
            return filtered
        elif excludes:
            for k in excludes:
                doc.pop(k, None)
            return doc
        return doc

    def _apply_update(self, doc: Dict[str, Any], update: Dict[str, Any]):
        if "$set" in update:
            for k, v in update["$set"].items():
                if ".$. " in k or ".$. " in k:
                    pass
                if ".$. " in k or ".$. " in k:
                    pass
                if ".$. " in k:
                    prefix, sub = k.split(".$.", 1)
                    arr = doc.get(prefix)
                    if isinstance(arr, list) and arr:
                        _set_nested(arr[0], sub, v)
                        continue
                _set_nested(doc, k, v)
        if "$push" in update:
            for k, v in update["$push"].items():
                _push_nested(doc, k, v)
        if "$addToSet" in update:
            for k, v in update["$addToSet"].items():
                parts = k.split(".")
                curr = doc
                for p in parts[:-1]:
                    if p not in curr or not isinstance(curr[p], dict):
                        curr[p] = {}
                    curr = curr[p]
                if parts[-1] not in curr or not isinstance(curr[parts[-1]], list):
                    curr[parts[-1]] = []
                if v not in curr[parts[-1]]:
                    curr[parts[-1]].append(copy.deepcopy(v))
        if "$inc" in update:
            for k, v in update["$inc"].items():
                cur_val = _get_nested(doc, k) or 0
                _set_nested(doc, k, cur_val + v)


class MockDatabase:
    def __init__(self, name: str = "mediconnect_phase6_test"):
        self.name = name
        self.collections: Dict[str, MockCollection] = {}

    def __getitem__(self, name: str) -> MockCollection:
        if name not in self.collections:
            self.collections[name] = MockCollection(name)
        return self.collections[name]

    def __getattr__(self, name: str) -> MockCollection:
        return self[name]

    def command(self, cmd: str, *args, **kwargs):
        if cmd == "ping":
            return {"ok": 1.0}
        return {"ok": 1.0}
