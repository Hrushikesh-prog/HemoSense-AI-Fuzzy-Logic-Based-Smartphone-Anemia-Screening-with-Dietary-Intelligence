import os
import glob
import cv2
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
import albumentations as A
from skimage.metrics import structural_similarity as ssim
from skimage.color import rgb2lab, deltaE_cie76

# ====================================================================
# PHASE 1.2 & 1.5: Data Structuring (Nested Folders) and Splitting
# ====================================================================
def build_master_dataframe(dataset_root):
    """
    Crawls the 'India' and 'Italy' folders, reads their respective Excel files,
    and maps every image inside the numbered folders to its Hgb value.
    """
    data = []
    regions = ['India', 'Italy']
    
    print(f"Scanning dataset root: {dataset_root}")
    
    for region in regions:
        region_path = os.path.join(dataset_root, region)
        if not os.path.exists(region_path):
            print(f"  [!] Could not find region folder: {region_path}")
            continue
            
        # Find the Excel or CSV file inside the region folder
        metadata_files = glob.glob(os.path.join(region_path, "*.xlsx")) + glob.glob(os.path.join(region_path, "*.csv"))
        
        if not metadata_files:
            print(f"  [!] No excel/csv file found in {region_path}")
            continue
            
        meta_file = metadata_files[0]
        print(f"  -> Found metadata for {region}: {os.path.basename(meta_file)}")
        
        # Read the file
        if meta_file.endswith('.csv'):
            df_meta = pd.read_csv(meta_file)
        else:
            df_meta = pd.read_excel(meta_file)
            
        # Find the column names for folder number and Hgb dynamically to prevent typos
        # Looks for columns containing "folder" or "number", and "hgb" or "hb"
        folder_col = [c for c in df_meta.columns if 'folder' in str(c).lower() or 'number' in str(c).lower()][0]
        hgb_col = [c for c in df_meta.columns if 'hgb' in str(c).lower() or 'hb' in str(c).lower()][0]
        
        # Loop through every patient in the excel sheet
        for index, row in df_meta.iterrows():
            try:
                # Get folder number and Hgb
                folder_num = str(int(row[folder_col]))
                hgb_val = float(row[hgb_col])
                
                # Path to this patient's images
                patient_folder = os.path.join(region_path, folder_num)
                
                if os.path.exists(patient_folder):
                    # Get all images in this folder
                    images = glob.glob(os.path.join(patient_folder, "*.*"))
                    for img_path in images:
                        if img_path.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                            data.append({
                                'image_path': img_path,
                                'hemoglobin_level': hgb_val,
                                'region': region
                            })
            except Exception as e:
                continue

    master_df = pd.DataFrame(data)
    if master_df.empty:
        print("\n[Error] Master dataframe is empty. Ensure images are in the numbered folders and Excel file is correct.")
    else:
        print(f"\n[Success] Built master dataset mapping! Found {len(master_df)} total images across {len(regions)} regions.")
    return master_df

def prepare_and_split_data(dataset_root):
    """
    Builds the dataframe, applies severity classes, and splits it.
    """
    df = build_master_dataframe(dataset_root)
    if df is None or df.empty:
        return None, None, None

    # 1. Create Severity Classes for Stratification
    bins = [0, 7.0, 10.0, 12.0, 30.0]
    labels = ['Severe', 'Moderate', 'Mild', 'Normal']
    df['severity_class'] = pd.cut(df['hemoglobin_level'], bins=bins, labels=labels)
    
    # 2. Train (70%), Val (15%), Test (15%) Split with Stratification
    try:
        train_df, temp_df = train_test_split(df, test_size=0.3, stratify=df['severity_class'], random_state=42)
        val_df, test_df = train_test_split(temp_df, test_size=0.5, stratify=temp_df['severity_class'], random_state=42)
    except ValueError:
        print("  [Warning] Some severity classes (e.g. Severe) have too few images to perfectly stratify. Falling back to random split.")
        train_df, temp_df = train_test_split(df, test_size=0.3, random_state=42)
        val_df, test_df = train_test_split(temp_df, test_size=0.5, random_state=42)
    
    print(f"\n[Phase 1.5] Data Split Complete:")
    print(f"Train: {len(train_df)} images | Val: {len(val_df)} images | Test: {len(test_df)} images")
    
    # Save the splits to CSVs in the dataset root for Phase 3!
    train_df.to_csv(os.path.join(dataset_root, "train_split.csv"), index=False)
    val_df.to_csv(os.path.join(dataset_root, "val_split.csv"), index=False)
    test_df.to_csv(os.path.join(dataset_root, "test_split.csv"), index=False)
    print(f"-> Saved split mappings to CSV files in: {dataset_root}")
    
    return train_df, val_df, test_df

# ====================================================================
# PHASE 1.3: Synthetic Augmentation Pipeline
# ====================================================================
def get_synthetic_augmentation_pipeline():
    return A.Compose([
        A.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2, hue=0.1, p=0.7),
        A.RandomShadow(p=0.5),
        A.ImageCompression(quality_range=(50, 90), p=0.5),
        A.GaussNoise(p=0.3)
    ])

def augment_image(image, pipeline):
    augmented = pipeline(image=image)
    return augmented['image']

# ====================================================================
# PHASE 2.6: Quantitative Validation (SSIM & Delta E)
# ====================================================================
def validate_correction_metrics(img_original, img_corrected):
    gray_orig = cv2.cvtColor(img_original, cv2.COLOR_BGR2GRAY)
    gray_corr = cv2.cvtColor(img_corrected, cv2.COLOR_BGR2GRAY)
    ssim_score, _ = ssim(gray_orig, gray_corr, full=True)
    
    lab_orig = rgb2lab(cv2.cvtColor(img_original, cv2.COLOR_BGR2RGB))
    lab_corr = rgb2lab(cv2.cvtColor(img_corrected, cv2.COLOR_BGR2RGB))
    delta_e = np.mean(deltaE_cie76(lab_orig, lab_corr))
    
    return ssim_score, delta_e

# ====================================================================
# BATCH EXECUTION PREVIEW
# ====================================================================
def run_batch_prep_preview():
    print("==================================================")
    print("PHASE 1 & 2: BATCH DATASET PREPARATION & VALIDATION")
    print("==================================================")
    
    # Ensure this points to the exact parent folder that holds the 'India' and 'Italy' subfolders
    dataset_dir = r"C:\Users\MCS.DESKTOP-744KNRC\Documents\PROJECTS\HemoSense AI Fuzzy Logic-Based Smartphone Anemia Screening with Dietary Intelligence\dataset\datasetanemia" 
    
    print("\nExecuting Phase 1.2 & 1.5 (Structuring & Splitting)...")
    train, val, test = prepare_and_split_data(dataset_dir)
    
    print("\nExecuting Phase 1.3 (Synthetic Augmentation)...")
    aug_pipeline = get_synthetic_augmentation_pipeline()
    print("Augmentation pipeline loaded: Shadows, Color Jitter, JPEG Compression, Noise.")
    
    print("\nExecuting Phase 2.6 (SSIM & Delta E Validation Setup)...")
    print("Validation metrics ready for computing SSIM and Delta E on the test set.")
    
    print("\n[NEXT STEP]: Phase 3! You now have train_split.csv, val_split.csv, and test_split.csv ready for your CNN.")

if __name__ == "__main__":
    run_batch_prep_preview()
