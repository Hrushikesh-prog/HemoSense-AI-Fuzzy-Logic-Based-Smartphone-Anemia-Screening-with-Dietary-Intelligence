# Literature Review - HemoSense AI

Status: compiled 2026-11-13. 23 papers. Every row was checked against a primary record: the full text (Europe PMC/PMC, PLOS, a publisher PDF) or the official abstract record (PubMed/Europe PMC, OpenAlex, Semantic Scholar, Crossref, IEEE DataPort).
Verification level per row: **[FT]** = full text read; **[ABS]** = abstract/official record only (numbers limited to what the abstract states); **[META]** = bibliographic record only.
"not verified" = could not be confirmed from an opened page. Several publisher sites (ScienceDirect, Wiley, MDPI, IEEE Xplore) blocked automated access, so a few rows are abstract-level only. **Before submission, open the [ABS]/[META] rows yourself and fill in the "not verified" cells.**

Abbreviations: Acc = accuracy, Sens = sensitivity, Spec = specificity, Hb = haemoglobin, CV = cross-validation, EI = erythema index, HHR = high hue ratio.

---

## 1. Summary tables

### 1A. Anaemia detection from conjunctiva images

| # | Paper | Body site / device | Dataset (name, size, country) | Method | Reported results (evaluation protocol) | Relevance to HemoSense | Level |
|---|---|---|---|---|---|---|---|
| [1] | Collings et al., 2016, PLoS ONE | Palpebral conjunctiva; Panasonic LX5 compact camera and iPhone 5S, ambient light, **in-frame colour calibration card** | 94 analysed (106 recruited) haemato-oncology patients, Wellington, New Zealand; 40% anaemic (Hb < 110 g/L) | Single feature: palpebral **erythema index** EI = log(S_red) - log(S_green); ROC-derived threshold | Compact camera: training Sens 93%, Spec 78%, AUC 0.90; **internal held-out validation (alternate allocation, 47/47)**: Sens 57%, Spec 83%, Acc 70%. iPhone validation Acc 72%. Clinicians: 57-64% Acc. EI vs Hb r^2 = 0.27 | Origin of our EI feature; shows that colour standardisation matters and that a single threshold generalises poorly | FT |
| [2] | Dimauro et al., 2023, Artificial Intelligence in Medicine 136:102477 | Palpebral and forniceal conjunctiva; low-cost smartphone-based device | **Eyes-defy-anemia** (Italian and Indian patients; dataset released publicly) | Machine learning on conjunctiva colour features; **RUSBoost** best on the palpebral region | Abstract reports "good performance" and robustness across ethnicities. **Exact metrics and validation protocol not verified** (full text blocked) | Primary benchmark dataset for us; RUSBoost handles class imbalance; key baseline to cite | ABS |
| [3] | Dimauro, Caivano, Girardi, 2018, IEEE Access 6:46968-46975 | Conjunctiva; purpose-built low-cost acquisition device | 113 anaemic and healthy persons, Italy (country inferred from authors' affiliation, not verified) | Colour values of a specific conjunctival region; Hb estimation; **k-NN** classifier | "Strong correlation" between estimated and lab Hb; k-NN "good results". Numbers and protocol not verified | Earlier pipeline from the Dimauro group: colour features, then a classical classifier | ABS |
| [4] | Appiahene et al., 2023, Medicine in Novel Technology and Devices 18:100244 | Palpebral conjunctiva (children) | **CP-AnemiC**: 710 children aged 6-59 months, 10 hospitals, Ghana; 424 anaemic / 286 non-anaemic (Hb < 11 g/dL) | Joint CNN/ViT network for classification plus Hb regression (ResNet50, VGG16, DenseNet121, ViT, ConvNeXt) | **5-fold CV**: ResNet50 Acc 84.79%, AUC 0.835; ViT Acc 84.08%, AUC 0.841, F1 0.833; Hb MAE 1.50 g/dL (ViT), 1.54 (ResNet50); ViT Bland-Altman bias 0.02, LoA -3.56 to 3.61 | Largest public conjunctiva set; realistic deep-learning ceiling (~84-85%) to compare against | FT |
| [5] | Suner et al., 2021, PLoS ONE 16:e0253495 | Palpebral conjunctiva; iPhone 7 Plus, RAW (Halide app), ambient light | 344 Emergency Department patients, Rhode Island Hospital, USA (142 derivation + 202 validation) | 26 image parameters, stepwise regression to estimated Hb | Derivation: Acc 82.9, Sens 90.7, Spec 73.3. **Separate prospective validation cohort**: Acc 72.6, Sens 72.8, Spec 72.5. Transfusion thresholds <7 / <9 g/dL: Acc 94.4 / 86. Skin tone did not affect results | Shows the drop from derivation to independent validation; image quality drives bias | FT |
| [6] | Zhao et al., 2024, PLoS ONE 19:e0302883 | Palpebral conjunctiva; iPhone X real-time app (RAW, no flash) | 435 ED patients, Rhode Island, USA | **High hue ratio (HHR)**, using a previously derived HHR to Hb model | Prospective evaluation: Acc 75.4% across anaemia categories; anaemia Sens 54.3, Spec 89.7, AUC 0.76 (sex-specific); AUC 0.92 (<7 g/dL) and 0.90 (<9 g/dL); Bland-Altman bias 0.10, LoA -4.73 to 4.93 g/dL | Source of our HHR feature; on-device real-time screening is feasible but has limited sensitivity at the anaemia threshold | FT |
| [7] | Chen, Miaou, Bian, 2016, Computer Methods and Programs in Biomedicine 137:125-135 | Palpebral conjunctiva | not verified | Feature 1: **high hue rate (HHR)** from HSI, then PVM (RGB), Mahalanobis classifier; Feature 2: entropy, binarised HHR and PVM, then SVM/ANN | Reported as sensitivity, specificity and kappa; values not verified | Early definition of the hue-ratio feature; hand-crafted features with a small classifier | ABS |
| [8] | Tamir et al., 2017, IEEE R10-HTC, pp. 697-701 | Anterior conjunctiva; smartphone with Android app | 19 subjects (Bangladesh; country not verified) | Red/green component spectra, fixed threshold | 15/19 agreed with blood report (Acc 78.9%); no separate test set | Simplest threshold baseline; very small sample | ABS |
| [9] | Kasiviswanathan et al., 2020, Electronics 9(8):1309 | Conjunctiva; consumer cameras, uncontrolled setting | not verified | Fine-tuned **U-Net** for conjunctiva segmentation | IoU 96% (training), 85.7% (validation) | Segmentation stage of our pipeline | ABS |
| [10] | Asare et al., 2023, Engineering Reports 5(11):e12667 | Conjunctiva, palm, fingernail (children) | Ghana; sizes not verified | CIELAB features; Naive Bayes, CNN, SVM, k-NN, decision tree | Best CNN Acc 99.12%; SVM lowest at 95.4%. Protocol not verified | CIELAB a* feature precedent. Treat the near-perfect accuracies cautiously (see [18]) | ABS |
| [11] | Sehar, Krishnamoorthi, Vinoth Kumar, 2025, Healthcare Informatics Research 31(1):57-65 | Palpebral conjunctiva; smartphone | 764 images (54 own iPhone, India + 710 from an online database), augmented to 4,315 with a DCGAN | SLIC segmentation; ML/DL; stacking ensemble (VGG16 + ResNet-50 + InceptionV3) | Stacking ensemble AUC 0.97; 80/10/10 split. Whether augmentation came before the split is not verified | Recent CNN ensemble baseline | FT |
| [12] | Ramos-Soto et al., 2025, Scientific Reports 15:44142 | Conjunctiva and sclera | Eyes-defy-anemia (217 usable images; 91 anaemia / 126 no anaemia) | **ViT** (ImageNet-21k transfer learning) with attention-map explainability; CNN baselines | Acc 98.47% on an 80/20 split (MobileNet-V2 94.66%). **Authors state that augmentation (flips) was applied before the split, so the test set holds orientation variants of training images**; no k-fold | Explainability baseline; also shows the data-leakage risk on small datasets | FT |
| [13] | Camporeale et al., 2025, Computers in Biology and Medicine 197:111026 | Palpebral conjunctiva | Repeated images of the same patients over several days (Dimauro/Maglietta group) | ViT with patient-specific "dual fine-tuning" | R^2 0.94, Acc 98%, MAE 0.25 g/dL, Sens 100% (personalised setting) | Personalised monitoring, not a population screening setting | ABS |

### 1B. Fuzzy logic / neuro-fuzzy (ANFIS) for anaemia and medical screening

| # | Paper | Input data | Dataset | Method | Results | Relevance | Level |
|---|---|---|---|---|---|---|---|
| [14] | Jang, 1993, IEEE Trans. Systems, Man, and Cybernetics 23(3):665-685 | n/a (method) | n/a | ANFIS: Sugeno-type fuzzy inference tuned by hybrid least-squares and gradient learning | n/a | Foundation of our data-tuned zero-order Sugeno model | META |
| [15] | Allahverdi et al., 2011, Expert Systems with Applications 38(6):7415-7418 | Laboratory/clinical data of children (not verified) | not verified | Takagi-Sugeno neuro-fuzzy network for child anaemia level | not verified (abstract withheld by publisher) | Direct precedent of neuro-fuzzy anaemia grading, but from laboratory data, not images | META |
| [16] | Azarkhish et al., 2012, Journal of Medical Systems 36:2057-2061 | Laboratory indices MCV, MCH, MCHC, Hb/RBC | not verified (Iran per affiliation; not verified) | ANN vs **ANFIS** vs logistic regression for iron-deficiency anaemia and serum iron | ANN outperformed ANFIS and LR; numbers not verified | ANFIS has been tried for anaemia only on blood indices; ANN beat it there, so our comparison must be fair | ABS |

### 1C. Other non-invasive smartphone sites (context)

| # | Paper | Body site | Dataset | Method | Results | Relevance | Level |
|---|---|---|---|---|---|---|---|
| [17] | Mannino et al., 2018, Nature Communications 9:4924 | Fingernail beds; unmodified smartphone, no calibration card | 337 enrolled, Atlanta, USA; 100-subject evaluation | Colour plus image metadata to Hb | Hb within +/-2.4 g/dL, bias 0.2; Sens 97% (Hb < 12.5 g/dL); personalised calibration +/-0.92 g/dL (n = 16) | Benchmark for card-free colour correction from metadata | FT |
| [18] | Appiahene et al., 2023, BioData Mining 16:2 | Palm (children) | Ghana, 10 hospitals; size not verified | CIELAB ROI; CNN, k-NN, NB, SVM, DT | NB Acc 99.96%, CNN 99.92%, SVM 96.34%. **Augmentation applied before the 70/10/20 split** (stated) | Palm context; illustrates inflated accuracies from augmenting before the split | FT |
| [19] | Donmez et al., 2023, Frontiers in Big Data 6:1241899 | Lip mucosa | 138 patients (100 women, 38 men) | RGB red and HSV saturation plus age/sex; ANN, DT, KNN, LR, NB, SVM | NB Acc 96%; DT/KNN/ANN 93%; LR 79%; SVM 75%; protocol not verified | Saturation feature precedent; lip site | ABS |

### 1D. Colour constancy / white balance in smartphone medical imaging

| # | Paper | Domain | Method | Results | Relevance | Level |
|---|---|---|---|---|---|---|
| [20] | Barata, Celebi, Marques, 2015, IEEE JBHI 19(3):1146-1152 | Dermoscopy, multi-source images | Gray World, max-RGB, Shades of Gray, General Gray World | Colour constancy raised Sens from 71.0% to 79.7% and Spec from 55.2% to 76% | Evidence that illuminant normalisation improves colour-feature classifiers | ABS |
| [21] | Outlaw et al., 2020, PLoS ONE 15:e0216970 | Neonatal jaundice from the **sclera**; smartphone, no calibration card | Flash/no-flash ambient subtraction, sclera chromaticity, one-time camera calibration | n = 37; r = 0.75 with serum bilirubin; Sens 100% / Spec 61% (TSB > 250 umol/L), AUROC 0.86 | Closest precedent for using the sclera as an in-image colour reference | ABS |
| [22] | Hu, Cheng, Lan, 2016, Journal of Medical Systems 40:18 | Tongue images from smartphones | SVM predicts the illuminant and colour-correction matrix from flash/no-flash difference | Better feature-detection accuracy under fluorescent, incandescent and halogen light (numbers not verified) | Learned colour correction for smartphone health imaging; also a tongue-site example | ABS |

### 1E. Diet / nutrition for iron-deficiency anaemia

| # | Paper | Type | Key content | Relevance | Level |
|---|---|---|---|---|---|
| [23] | Hurrell & Egli, 2010, American Journal of Clinical Nutrition 91(5):1461S-1467S | Review | Iron bioavailability about 14-18% (mixed diets) vs 5-12% (vegetarian diets); enhancers (ascorbic acid, muscle tissue) and inhibitors (phytate, polyphenols, calcium); host iron status matters more than diet composition | Evidence base for the diet-recommendation rules (pair iron with vitamin C, avoid tea/calcium at meals) | ABS |

**Gap in this section:** only one diet source is verified so far. Before submission, add and verify (a) the WHO guidance on anaemia/iron (e.g. WHO Hb thresholds and nutritional-anaemia guidance) and (b) at least one food-recommender-system paper. A candidate found but **not yet read** is Yera et al., 2023, IJERPH 20:4248, "A Systematic Review on Food Recommender Systems for Diabetic Patients" (DOI 10.3390/ijerph20054248).

---

## 2. Related Work (draft, about 560 words)

Pallor of the palpebral conjunctiva is a long-established clinical sign of anaemia, and several groups have sought to quantify it from digital photographs. Collings et al. [1] derived a conjunctival erythema index from calibrated photographs and reported a sensitivity of 93% and specificity of 78% in a training set, which fell to 57% and 83% on an internal validation set. Chen et al. [7] proposed the high hue rate feature in HSI space, and Tamir et al. [8] applied a fixed threshold to the red and green components of smartphone images, although on only 19 subjects. Suner et al. [5] built a regression model from smartphone RAW images in an emergency department; accuracy fell from 82.9% in the derivation phase to 72.6% in a separate validation cohort. Zhao et al. [6] then ran a real-time high-hue-ratio app prospectively on 435 patients, with an AUC of 0.76 at the anaemia threshold and 0.90-0.92 at transfusion thresholds. Dimauro and colleagues built a low-cost acquisition device with k-NN classification [3] and later released the Eyes-defy-anemia dataset of Italian and Indian patients, for which a RUSBoost classifier trained on palpebral features was reported to perform well across ethnicities [2]. Conjunctiva segmentation has been addressed with U-Net, reaching a validation IoU of 85.7% [9].

Deep learning has followed. On the CP-AnemiC dataset of 710 Ghanaian children, joint CNN and Vision Transformer models reached about 84-85% accuracy and a haemoglobin MAE of 1.50 g/dL under five-fold cross-validation [4]. Other studies report accuracies above 98% with ViTs [12] and CNN ensembles [11], or with classical classifiers on CIELAB features [10], [18]. Some of these figures should be read with care: in [12] and [18] the authors state that augmentation was applied before the train-test split, which can let near-duplicate images leak into the test set. Personalised ViT models with repeated per-patient images reach an MAE of 0.25 g/dL [13], but this addresses longitudinal monitoring rather than population screening.

Other body sites give context. Mannino et al. [17] estimated haemoglobin from fingernail-bed photographs using colour and image metadata, reaching 97% sensitivity without calibration cards. Palm [18] and lip-mucosa [19] images have also been classified with conventional machine learning.

Fuzzy and neuro-fuzzy methods have been applied to anaemia mainly through laboratory data. Allahverdi et al. [15] used a Takagi-Sugeno neuro-fuzzy network to grade anaemia in children. Azarkhish et al. [16] compared ANFIS [14] with neural networks and logistic regression on red-cell indices and found the neural network superior. We did not find, among the studies reviewed here, any that applies data-tuned fuzzy inference to conjunctival colour features.

Illumination variability is a recurring confound. Collings et al. [1] used an in-frame calibration card. Mannino et al. [17] used image metadata instead. In dermoscopy, colour-constancy algorithms such as Shades of Gray raised sensitivity from 71.0% to 79.7% [20]. Outlaw et al. [21] used the sclera with flash/no-flash ambient subtraction for jaundice screening, and Hu et al. [22] learned colour-correction matrices for smartphone tongue images. On the intervention side, iron bioavailability depends strongly on dietary enhancers and inhibitors and on host iron status [23], which motivates diet guidance tailored to the screening result.

---

## 3. Research gap

The reviewed literature suggests three gaps that HemoSense AI targets. First, conjunctiva-based anaemia screening has relied either on single-feature thresholds [1], [6], [8] or on opaque classifiers [2], [4], [11], [12]. Fuzzy and ANFIS models have been applied to anaemia only with laboratory blood indices [15], [16], so a data-tuned, rule-readable fuzzy model over interpretable colour features (erythema index, CIELAB a*, high hue ratio, saturation) appears not to have been evaluated against logistic-regression, random-forest and CNN baselines on public conjunctiva datasets. Second, colour correction in this domain has relied mainly on calibration cards [1] or controlled-light devices [2], [3]. Sclera-referenced white balance, which has precedent in jaundice screening [21], appears untested for anaemia, at least in the studies we reviewed. Third, none of the reviewed screening systems links its output (probability and severity) to nutritional guidance grounded in iron-bioavailability evidence [23]. We also note that high reported accuracies on small datasets may be inflated by augmentation before splitting [12], [18]. This motivates our use of patient-level held-out evaluation, so that our results are not directly comparable with those figures. These gaps come from a 23-paper review and should not be read as claims of absolute novelty.

---

## 4. References (IEEE style)

[1] S. Collings, O. Thompson, E. Hirst, L. Goossens, A. George, and R. Weinkove, "Non-invasive detection of anaemia using digital photographs of the conjunctiva," *PLoS ONE*, vol. 11, no. 4, Art. no. e0153286, 2016, doi: 10.1371/journal.pone.0153286. https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0153286

[2] G. Dimauro, M. E. Griseta, M. G. Camporeale, F. Clemente, A. Guarini, and R. Maglietta, "An intelligent non-invasive system for automated diagnosis of anemia exploiting a novel dataset," *Artificial Intelligence in Medicine*, vol. 136, Art. no. 102477, 2023, doi: 10.1016/j.artmed.2022.102477. https://pubmed.ncbi.nlm.nih.gov/36710064/

[3] G. Dimauro, D. Caivano, and F. Girardi, "A new method and a non-invasive device to estimate anemia based on digital images of the conjunctiva," *IEEE Access*, vol. 6, pp. 46968-46975, 2018, doi: 10.1109/ACCESS.2018.2867110.

[4] P. Appiahene, K. Chaturvedi, J. W. Asare, E. T. Donkoh, and M. Prasad, "CP-AnemiC: A conjunctival pallor dataset and benchmark for anemia detection in children," *Medicine in Novel Technology and Devices*, vol. 18, Art. no. 100244, 2023, doi: 10.1016/j.medntd.2023.100244.

[5] S. Suner et al., "Prediction of anemia and estimation of hemoglobin concentration using a smartphone camera," *PLoS ONE*, vol. 16, no. 7, Art. no. e0253495, 2021, doi: 10.1371/journal.pone.0253495. https://europepmc.org/article/PMC/PMC8279386

[6] L. Zhao et al., "Prediction of anemia in real-time using a smartphone camera processing conjunctival images," *PLoS ONE*, vol. 19, Art. no. e0302883, 2024, doi: 10.1371/journal.pone.0302883. https://europepmc.org/article/PMC/PMC11090304

[7] Y.-M. Chen, S.-G. Miaou, and H. Bian, "Examining palpebral conjunctiva for anemia assessment with image processing methods," *Computer Methods and Programs in Biomedicine*, vol. 137, pp. 125-135, 2016, doi: 10.1016/j.cmpb.2016.08.025.

[8] A. Tamir et al., "Detection of anemia from image of the anterior conjunctiva of the eye by image processing and thresholding," in *Proc. IEEE Region 10 Humanitarian Technology Conf. (R10-HTC)*, 2017, pp. 697-701, doi: 10.1109/R10-HTC.2017.8289053.

[9] S. Kasiviswanathan, T. B. Vijayan, L. Simone, and G. Dimauro, "Semantic segmentation of conjunctiva region for non-invasive anemia detection applications," *Electronics*, vol. 9, no. 8, Art. no. 1309, 2020, doi: 10.3390/electronics9081309.

[10] J. W. Asare, P. Appiahene, E. T. Donkoh, and G. Dimauro, "Iron deficiency anemia detection using machine learning models: A comparative study of fingernails, palm and conjunctiva of the eye images," *Engineering Reports*, vol. 5, no. 11, Art. no. e12667, 2023, doi: 10.1002/eng2.12667.

[11] N. Sehar, N. Krishnamoorthi, and C. Vinoth Kumar, "Deep learning model-based detection of anemia from conjunctiva images," *Healthcare Informatics Research*, vol. 31, no. 1, pp. 57-65, 2025, doi: 10.4258/hir.2025.31.1.57. https://europepmc.org/article/PMC/PMC11854623

[12] O. Ramos-Soto, J. Ramos-Frutos, E. Perez-Zarate, D. Oliva, S. J. Mousavirad, and S. E. Balderas-Mata, "Non-invasive anemia detection from conjunctiva and sclera images using vision transformer with attention map explainability," *Scientific Reports*, vol. 15, Art. no. 44142, 2025, doi: 10.1038/s41598-025-32343-w. https://europepmc.org/article/PMC/PMC12717107

[13] M. Camporeale et al., "Highly reliable personalized noninvasive hemoglobin estimation by using Vision Transformers and dual fine-tuning," *Computers in Biology and Medicine*, vol. 197, Art. no. 111026, 2025, doi: 10.1016/j.compbiomed.2025.111026.

[14] J.-S. R. Jang, "ANFIS: Adaptive-network-based fuzzy inference system," *IEEE Transactions on Systems, Man, and Cybernetics*, vol. 23, no. 3, pp. 665-685, 1993, doi: 10.1109/21.256541.

[15] N. Allahverdi, A. Tunali, H. Isik, and H. Kahramanli, "A Takagi-Sugeno type neuro-fuzzy network for determining child anemia," *Expert Systems with Applications*, vol. 38, no. 6, pp. 7415-7418, 2011, doi: 10.1016/j.eswa.2010.12.083.

[16] I. Azarkhish, M. R. Raoufy, and S. Gharibzadeh, "Artificial intelligence models for predicting iron deficiency anemia and iron serum level based on accessible laboratory data," *Journal of Medical Systems*, vol. 36, pp. 2057-2061, 2012, doi: 10.1007/s10916-011-9668-3.

[17] R. G. Mannino et al., "Smartphone app for non-invasive detection of anemia using only patient-sourced photos," *Nature Communications*, vol. 9, Art. no. 4924, 2018, doi: 10.1038/s41467-018-07262-2. https://europepmc.org/article/PMC/PMC6279826

[18] P. Appiahene, J. W. Asare, E. T. Donkoh, G. Dimauro, and R. Maglietta, "Detection of iron deficiency anemia by medical images: A comparative study of machine learning algorithms," *BioData Mining*, vol. 16, Art. no. 2, 2023, doi: 10.1186/s13040-023-00319-z. https://europepmc.org/article/PMC/PMC9875467

[19] T. B. Donmez, M. Mansour, M. Kutlu, C. Freeman, and S. Mahmud, "Anemia detection through non-invasive analysis of lip mucosa images," *Frontiers in Big Data*, vol. 6, Art. no. 1241899, 2023, doi: 10.3389/fdata.2023.1241899.

[20] C. Barata, M. E. Celebi, and J. S. Marques, "Improving dermoscopy image classification using color constancy," *IEEE Journal of Biomedical and Health Informatics*, vol. 19, no. 3, pp. 1146-1152, 2015, doi: 10.1109/JBHI.2014.2336473.

[21] F. Outlaw, M. Nixon, O. Odeyemi, L. W. MacDonald, J. Meek, and T. S. Leung, "Smartphone screening for neonatal jaundice via ambient-subtracted sclera chromaticity," *PLoS ONE*, vol. 15, no. 3, Art. no. e0216970, 2020, doi: 10.1371/journal.pone.0216970.

[22] M.-C. Hu, M.-H. Cheng, and K.-C. Lan, "Color correction parameter estimation on the smartphone and its application to automatic tongue diagnosis," *Journal of Medical Systems*, vol. 40, Art. no. 18, 2016, doi: 10.1007/s10916-015-0387-z.

[23] R. Hurrell and I. Egli, "Iron bioavailability and dietary reference values," *American Journal of Clinical Nutrition*, vol. 91, no. 5, pp. 1461S-1467S, 2010, doi: 10.3945/ajcn.2010.28674F.

---

## 5. Public datasets encountered

| Dataset | Size | Labels | Access |
|---|---|---|---|
| Eyes-defy-anemia (Dimauro, Maglietta, Bai, Kasiviswanathan, 2022) | 218 conjunctiva images: 123 Italy (Bari), 95 India (Chennai); Samsung S6 with magnifying, light-controlled attachment | Lab Hb, age, sex; manual masks (palpebral, forniceal, combined); one patient has no Hb | IEEE DataPort, DOI 10.21227/t5s2-4j73, https://ieee-dataport.org/documents/eyes-defy-anemia (CC BY 4.0; login/subscription required for download) |
| CP-AnemiC (Appiahene et al., 2023) | 710 children aged 6-59 months, 10 Ghanaian hospitals; 424 anaemic / 286 non-anaemic | Hb (g/dL), anaemia label (Hb < 11 g/dL) | Mendeley Data, https://data.mendeley.com/datasets/m53vz6b7fx (academic use; v2 notes possible duplicates, so run quality checks) |
| Related Ghana conjunctiva set (same group) | 710 images; 4,260 after augmentation (per search listing; not opened) | not verified | https://data.mendeley.com/datasets/nt7r8hv2pz (not verified) |
