---
title: "Multiple Instance Learning: A Comprehensive Guide"
date: 2026-04-03
author: "Dennis Loevlie"
tags: ["Multiple Instance Learning", "Deep Learning", "Computational Pathology", "PyTorch"]
excerpt: "What is Multiple Instance Learning? A guide to MIL with PyTorch code, interactive demos, and real brain MRI examples."
image: "portfolio/images/blog/mil-cover.jpg"
series: "Deep Dive: Multiple Instance Learning"
series_order: 1
draft: false
---

## What is Multiple Instance Learning?

**Multiple Instance Learning (MIL) is a type of weakly supervised learning where labels are assigned to groups of instances (called bags) rather than to individual instances.** It is widely used in medical imaging, computational pathology, drug discovery, and text classification.

In standard supervised learning, we have a dataset of labeled instances: each input $x_i$ has a corresponding label $y_i$. But what happens when you only have labels for *groups* of instances, not the individual instances themselves?

This is the **Multiple Instance Learning (MIL)** setting. Instead of labeled instances, we have labeled **bags**. Each bag contains a set of instances, and only the bag has a label.

The classic formulation:

$$B_i = \{x_{i1}, x_{i2}, \ldots, x_{iK}\}, \quad Y_i \in \{0, 1\}$$

where $B_i$ is the $i$-th bag containing $K$ instances, and $Y_i$ is the bag-level label.

The key insight is that even though we only observe $Y_i$, we assume each instance $x_{ij}$ has a *latent* (unobserved) label $y_{ij} \in \{0, 1\}$. This lets us define the bag label in terms of instance labels:

$$Y_i = \max_{j=1}^{K} y_{ij}$$

In other words, a bag is positive if *any* of its instances are positive.

The **standard MIL assumption** follows directly:

- A bag is **positive** ($Y_i = 1$) if it contains **at least one** positive instance
- A bag is **negative** ($Y_i = 0$) if **all** instances are negative

<div class="alt-explain" x-data="{ open: false }">
<button class="alt-explain-btn" @click="open = !open">
<svg class="alt-explain-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
Another way to think about it
</button>
<div class="alt-explain-body" :style="open ? 'grid-template-rows: 1fr' : ''">
<div class="alt-explain-content">
<p>Think of it like a keychain. If at least one key on the ring opens the door, the keychain is "positive." You don't know <em>which</em> key works — you just know the keychain as a whole either works or doesn't.</p>
<p>Or consider a medical test: a patient (bag) provides multiple tissue samples (instances). If <em>any</em> sample shows disease, the patient is diagnosed as positive. The doctor records the patient-level diagnosis, not a label for each individual sample.</p>
</div>
</div>
</div>

## Why Does MIL Matter?

MIL is the natural formulation for many real-world problems where instance-level labels are expensive, ambiguous, or impossible to obtain.

### Medical Imaging

This is where I first encountered MIL during my M.S. at Tufts, working with [Michael Hughes](https://www.michaelchughes.com/) on <span class="term">deep<span class="term-tip">All we mean by "deep" here is that it involves using deep neural networks as the function approximator, rather than traditional ML methods like SVMs or random forests.</span></span> multiple instance learning for brain CT and MRI scans.

A brain scan consists of a stack of **axial slices**: 2D cross-sections taken from the bottom of the brain to the top, like slicing a loaf of bread. A single scan can have **100+ slices**, and the radiologist's diagnosis (e.g., presence of a hemorrhage) applies to the entire scan, not individual slices.

This is a natural MIL problem:

1. Each **axial slice** is an **instance**
2. The full stack of slices from one scan is a **bag**
3. The scan-level diagnosis is the **bag label**
4. A scan is positive if **at least one slice** shows the finding

<div id="brain-slice-demo" class="mil-demo-container"></div>

*Example of a **positive bag**: a brain scan (bag) where one axial slice (instance) contains a finding (red highlight). MRI data from the [Harvard Whole Brain Atlas](https://www.med.harvard.edu/aanlib/).*

MIL shows up throughout medical imaging. In **computational pathology**, the same idea applies at a different scale. A whole-slide image (WSI) can be `100,000 × 100,000` pixels, but typical <span class="term">encoders<span class="term-tip">A function that maps an input to a lower-dimensional embedding. Usually a pretrained architecture like ViT or ResNet, trained on ImageNet or a medical image dataset.</span></span> only handle inputs around `512×512`. MIL bridges this gap: tile the WSI into patches, encode each patch independently, and aggregate the embeddings for a slide-level prediction.

### Other Applications

- **Drug discovery**: A molecule (bag) is a collection of conformations (instances). The molecule is active if at least one conformation binds.
- **Text classification**: A document (bag) is a collection of paragraphs (instances). The document is positive if at least one paragraph contains the relevant topic.
- **Image classification**: An image (bag) is a set of regions (instances). The image is positive if at least one region contains the object of interest.

## The MIL Framework

### Instance-Level vs. Embedding-Level Approaches

There are two fundamental approaches to MIL:

**Instance-level methods** classify each instance individually, then aggregate predictions. For example, mean pooling over raw instances:

$$\hat{Y} = g\left(\frac{1}{K}\sum_{k=1}^{K} x_k\right)$$

Or max pooling over per-instance predictions:

$$\hat{Y} = \max_{k=1}^{K} g(x_k)$$

Simple, but these operate directly on the inputs without learning useful representations first.

**Embedding-level methods** first encode each instance into a learned representation, then aggregate and classify:

$$\hat{Y} = g\left(\text{AGGREGATE}(f(x_1), f(x_2), \ldots, f(x_K))\right)$$

where $f$ is an instance <span class="term">encoder<span class="term-tip">A function that maps each instance to a fixed-size vector representation (embedding). This is typically a neural network like a CNN or transformer.</span></span> and $g$ is a classifier. You can still use mean or max pooling here, but now over learned embeddings rather than raw inputs. The key question is: **what aggregation function should we use?**

### Common Aggregation Functions

| Method | Aggregation | Pros | Cons |
|--------|------------|------|------|
| Max pooling | $\max_k h_k$ | Simple, respects MIL assumption | Ignores all but one instance |
| Mean pooling | $\frac{1}{K}\sum_k h_k$ | Uses all instances | Dilutes signal from rare positive instances |
| Attention | $\sum_k a_k h_k$ | Learns instance importance | More parameters, harder to train |

<div id="mil-interactive-demo" class="mil-demo-container"></div>

**Try it yourself**: drag the instances to see how their positions affect the **mean-pooled** bag embeddings (◆) and the decision boundary. Curious how that boundary line gets computed? Check out our [Logistic Regression with PyTorch](/blog/logistic-regression-pytorch/) post.

## A Simple MIL Model in PyTorch

Let's implement a basic MIL model with mean pooling:

```python
import torch
import torch.nn as nn
from torchvision.models import vit_b_16, ViT_B_16_Weights

class SimpleMIL(nn.Module):
    def __init__(self, num_classes=1):
        super(SimpleMIL, self).__init__()
        # Pretrained ViT encoder (frozen)
        vit = vit_b_16(weights=ViT_B_16_Weights.DEFAULT)
        self.f = nn.Sequential(*list(vit.children())[:-1])
        for param in self.f.parameters():
            param.requires_grad = False

        # Bag-level classifier
        self.g = nn.Sequential(
            nn.Linear(768, 128),
            nn.ReLU(),
            nn.Linear(128, num_classes),
            nn.Sigmoid(),
        )

    def forward(self, bag):
        # bag: (K, 3, 224, 224) — K image patches
        h = self.f(bag)             # (K, 768) — ViT embeddings
        z = h.mean(dim=0)           # (768,) — mean pooling
        y = self.g(z)               # (1,)
        return y
```

Here's a visual breakdown of this forward pass. Swapping out the aggregation step (mean pooling here) for a different method is what gives you different embedding-level MIL approaches.

<div id="mil-pipeline-demo" class="mil-demo-container" style="min-height: 200px; grid-column: 1 / -1;"></div>

This model:
1. Encodes each image instance through a frozen pretrained ViT
2. Aggregates the 768-dim embeddings via mean pooling
3. Classifies the aggregated bag representation

### Training Loop

```python
model = SimpleMIL()
criterion = nn.BCELoss()
optimizer = torch.optim.Adam(model.g.parameters(), lr=1e-3)  # only train classifier

for epoch in range(100):
    for bag, label in dataloader:  # bag: (K, 3, 224, 224)
        optimizer.zero_grad()
        pred = model(bag)
        loss = criterion(pred, label)
        loss.backward()
        optimizer.step()
```

## The Problem with Simple Pooling

Consider a brain scan with 50 axial slices. Only 3 slices show signs of a tumor. Mean pooling averages all 50 slice embeddings equally, so the signal from those 3 abnormal slices gets diluted by 47 healthy ones. Max pooling only looks at the single most extreme slice, ignoring that the tumor spans multiple adjacent slices.

What if the model could learn to **pay attention** to the slices that matter?

This is exactly what **attention-based MIL** does, and it's the subject of the next post in this series.

## What's Next

This is the first post in the **Deep Dive: Multiple Instance Learning** series. Coming up:

1. **This post**: What is MIL and why it matters
2. **Attention-Based MIL**: The Ilse et al. (2018) architecture that changed the field
3. **Transformer MIL**: How self-attention and transformers are pushing MIL forward
4. **MIL in Practice**: Lessons learned from real-world medical imaging

## Additional Resources

- [Attention-Based Deep Multiple Instance Learning (Ilse et al., 2018)](https://arxiv.org/abs/1802.04712) - The foundational attention MIL paper
- [TorchMIL](https://github.com/Franblueee/torchmil) - A PyTorch library for MIL (I'm a contributor)
- [CLAM: Data-efficient and weakly supervised computational pathology](https://arxiv.org/abs/2004.09666) - Widely used MIL framework for pathology
- [Multiple Instance Learning: A Survey (Carbonneau et al.)](https://arxiv.org/abs/1612.03365) - Comprehensive MIL review
