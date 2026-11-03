//! Independently authored regression, run unchanged against upstream and patch.
use bytes::Bytes;
use pacs_core::BlobStore;
use pacs_fs_storage::{FilesystemStorageConfig, FsBlobStore};

#[tokio::test]
async fn conflicting_sop_must_preserve_original() {
    let dir = tempfile::tempdir().expect("temporary synthetic store");
    let store = FsBlobStore::new(&FilesystemStorageConfig {
        root: dir.path().to_string_lossy().to_string(),
    }).expect("filesystem store");
    let key = "2.25.901/2.25.902/2.25.903";
    let original = Bytes::from_static(b"independently authored original storage bytes");
    store.put(key, original.clone()).await.expect("original creation");
    let conflict = store.put(key, Bytes::from_static(b"independently authored conflicting bytes")).await;
    assert!(conflict.is_err(), "same SOP content conflict must be rejected");
    assert_eq!(store.get(key).await.expect("original retrieval"), original,
               "a rejected conflict must preserve original bytes");
}
