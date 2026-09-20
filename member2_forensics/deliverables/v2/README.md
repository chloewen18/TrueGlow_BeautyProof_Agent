BeautyProof — Member 2 TruFor Deliverables



1\. Overview



This folder contains the TruFor-based image integrity analysis and experimental results completed by Member 2 for the BeautyProof project.



The main objectives were:



\* Set up and run the official TruFor model.

\* Perform image integrity inference.

\* Obtain image-level integrity scores.

\* Obtain localization and confidence maps.

\* Construct JPEG-compression hard negatives.

\* Analyze false-positive behavior under different thresholds.

\* Convert TruFor’s integrity score into a directionally consistent BeautyProof suspicion score.

\* Organize reproducible inference code, model weights, outputs, and experimental reports.



⸻



2\. Directory Structure



Member2\_TruFor\_Deliverables

│

├─False\_Positive\_Report

│      report.md

│      threshold\_analysis.csv

│

├─\_Hard\_Negatives

│      hard\_negative\_results.csv

│

├─\_Inference

│  ├─inference\_code

│  │      project\_config.py

│  │      test.py

│  │      visualize.py

│  │

│  └─official\_weights

│          trufor.pth.tar

│

├─\_Output

│  ├─npz

│  │      TruFor inference outputs

│  │

│  └─visualizations

│          TruFor visualization results

│

└─\_Score\_Direction

&#x20;       score\_conversion.csv



⸻



3\. Inference



Inference Environment



\* Operating System: Windows

\* Conda environment: beautyproof

\* Inference device: CPU

\* GPU was not required for the completed experiments.



For CPU inference, TruFor was executed with GPU index -1.



Inference Code



The reproducibility-related code is stored in:



\_Inference

└─inference\_code

&#x20;   ├─project\_config.py

&#x20;   ├─test.py

&#x20;   └─visualize.py



Official Model Weight



The official TruFor main model weight used in the experiment is:



\_Inference

└─official\_weights

&#x20;   └─trufor.pth.tar



⸻



4\. TruFor Output



TruFor inference produces .npz files rather than directly producing visualization images.



The outputs are stored in:



\_Output

└─npz



The main fields observed in the generated .npz files include:



\* map — localization-related output map

\* conf — confidence map

\* score — image-level integrity score

\* imgsize — image size information



The localization and confidence maps were generated at a spatial resolution of 1024 × 1024 in the tested outputs.



⸻



5\. Visualization



Visualization results are stored in:



\_Output

└─visualizations



The visualization results provide a visual representation of:



\* Input image

\* Localization map

\* Confidence map

\* TruFor score



The visualization script used for this purpose is:



\_Inference

└─inference\_code

&#x20;   └─visualize.py



The visualization files are provided as supplementary evidence for selected experimental cases.



⸻



6\. Hard Negative Experiment



The hard-negative experiment was designed to examine whether JPEG compression could change TruFor’s response even when the underlying image content remained unchanged.



The experiment used FFHQ face images in three conditions:



1\. Original image

2\. JPEG quality 50

3\. JPEG quality 20



The results are stored in:



\_Hard\_Negatives

└─hard\_negative\_results.csv



The experiment showed that JPEG compression can substantially change the TruFor integrity score.



For the tested Face03–Face10 pairs:



\* Q50 increased the score for 8/8 images.

\* Q20 increased the score for 7/8 images.

\* The magnitude of the change varied substantially across images.



The effect was therefore image-dependent and non-monotonic.



These results indicate that image compression should be considered when evaluating TruFor-based image integrity signals.



⸻



7\. Score Direction Conversion



TruFor provides an integrity-oriented score.



For integration into the BeautyProof pipeline, a directionally converted score was calculated as:



BeautyProof Suspicion Score

= 1 - TruFor Integrity Score



The converted results are stored in:



\_Score\_Direction

└─score\_conversion.csv



Important Note



The converted value is a directional score, not a calibrated probability.



Therefore:



BeautyProof Suspicion Score ≠ Manipulation Probability



The conversion only changes the direction of the score so that a larger value corresponds to greater suspicion.



A formal probability calibration would require an appropriate labeled validation dataset.



⸻



8\. False Positive Analysis



A preliminary threshold analysis was conducted using pristine images and JPEG-compressed hard negatives.



The results are stored in:



False\_Positive\_Report

├─threshold\_analysis.csv

└─report.md



The analysis examined false-positive counts at several thresholds.



Selected results:



Threshold	Pristine FP	Q50 FP	Q20 FP

0.20	4/10	9/10	10/10

0.30	3/10	6/10	8/10

0.40	1/10	4/10	4/10

0.50	1/10	2/10	3/10

0.60	0/10	1/10	1/10

0.70	0/10	0/10	0/10

0.80	0/10	0/10	0/10

0.90	0/10	0/10	0/10



One tampered example was also tested:



tampered1

TruFor Integrity Score ≈ 0.9976



This analysis is preliminary and is not intended to establish a final production threshold.



⸻



9\. Key Experimental Findings



9.1 JPEG compression affects TruFor scores



The same underlying image can receive substantially different integrity scores after JPEG compression.



Therefore, compression artifacts may influence the behavior of an integrity-detection model.



9.2 The effect is image-dependent



Different images respond differently to Q50 and Q20 compression.



The score change is not strictly proportional to JPEG quality.



Therefore, the experiment does not support the conclusion that stronger compression always produces a higher or lower TruFor score.



9.3 Hard negatives are important



JPEG-compressed pristine images can act as useful hard negatives because they preserve the underlying image content while introducing common real-world image-processing artifacts.



9.4 Score conversion does not equal probability calibration



The transformation:



1 - TruFor Integrity Score



is useful for score-direction consistency, but it does not establish a statistically calibrated probability of manipulation.



⸻



10\. Limitations



The current experiments have several limitations:



\* The sample size is small.

\* Only a limited number of pristine and JPEG-compressed images were tested.

\* The false-positive analysis contains only one tampered example.

\* No large-scale benchmark was conducted.

\* No formal probability calibration was performed.

\* The experiments do not establish a final production threshold.

\* JPEG compression is only one category of possible real-world perturbation.



Therefore, the current results should be treated as an exploratory engineering evaluation rather than a final model-performance benchmark.



⸻



11\. Deliverables



The current Member 2 deliverables include:



Inference



\_Inference



Contains the inference-related Python code and official TruFor model weight.



Raw Model Outputs



\_Output

└─npz



Contains the .npz outputs generated by TruFor inference.



Visualization



\_Output

└─visualizations



Contains selected visualization results.



Hard Negatives



\_Hard\_Negatives

└─hard\_negative\_results.csv



Contains paired original/Q50/Q20 experimental results.



Score Direction



\_Score\_Direction

└─score\_conversion.csv



Contains the directionally converted BeautyProof suspicion scores.



False Positive Analysis



False\_Positive\_Report

├─threshold\_analysis.csv

└─report.md



Contains threshold-based false-positive analysis and the corresponding experimental report.



⸻



12\. Conclusion



This deliverable package provides a reproducible TruFor inference setup together with raw outputs, visualization examples, hard-negative experiments, score-direction conversion, and preliminary false-positive analysis.



The experiments provide evidence that common image-processing operations such as JPEG compression can materially affect image-integrity scores. This should be considered when integrating TruFor into the broader BeautyProof image-authenticity pipeline.



The current results are intended to support subsequent dataset expansion, threshold calibration, hard-negative mining, and multi-signal fusion in future stages of the BeautyProof project.

