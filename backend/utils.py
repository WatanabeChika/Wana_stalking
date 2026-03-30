
def get_exact_bucket_id(aw, prefix):
    """安全获取本地真实的 Bucket ID"""
    try:
        buckets = aw.get_buckets()
        matching_buckets = [b_id for b_id in buckets.keys() if b_id.startswith(prefix)]
        return matching_buckets[0] if matching_buckets else None
    except Exception:
        return None