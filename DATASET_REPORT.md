# Dataset report

**Verified:** `C:\Users\Admin\Downloads\32_sounds_BigSoundBank.com.zip` was inspected, decoded, and segmented into `data/datasets/v1/`.

```
accessible: true
entries: 32
audio_files: 32 (.mp3)
decoded_wav_files: 32
segmented_events_and_clips: 97
distinct_groups (dog_id): 15
status: INSPECTED & PREPARED
```

## Summary of contents

- **21 Canine vocalization recordings (`ANMLDog_*`)**: indoor/outdoor barks, small dog/spitz barks and yips, multi-dog bark + growl recordings (`ID 1060`, `ID 1061`), barking and crying/whining (`ID 1544–1546`), old dog barks (`ID 2352–2354`), dog howling/singing (`ID 2450–2451`), pack barks (`ID 2953–2955`), behind-door barks (`ID 3537`).
- **11 Non-vocalization / household / mechanical recordings**: dog breathing/panting (`ID 1547`), cat/dog water fountain (`ID 0717`), and 9 mechanical squeaker toys (`TOYMech_Pouet of a toy`, `TOYMech_Squeaker toy 2`, `TOYMech_Couinement jouet 1–8`), mapped to `other`.

## Commands

```powershell
python backend/app/ml/inspect_dataset.py --out data/datasets/inspect.json
python backend/app/ml/prepare_dataset.py
python backend/app/ml/validate_annotations.py --manifest data/datasets/v1/manifest.csv
```
