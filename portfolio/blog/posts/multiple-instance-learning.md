---
title: "Multiple Instance Learning: A Comprehensive Guide"
date: 2026-04-03
author: "Dennis Loevlie"
tags: ["Multiple Instance Learning", "Deep Learning", "Computational Pathology", "PyTorch"]
excerpt: "A deep dive into Multiple Instance Learning — what it is, why it matters, and how to implement it in PyTorch. The first post in a series breaking down MIL architectures."
image: "portfolio/images/blog/mil-cover.jpg"
series: "Deep Dive: Multiple Instance Learning"
series_order: 1
draft: false
---

## What is Multiple Instance Learning?

In standard supervised learning, we have a dataset of labeled instances: each input $x_i$ has a corresponding label $y_i$. But what happens when you only have labels for *groups* of instances, not the individual instances themselves?

This is the **Multiple Instance Learning (MIL)** setting. Instead of labeled instances, we have labeled **bags** — each bag contains a set of instances, and only the bag has a label.

The classic formulation:

$$B = \{x_1, x_2, \ldots, x_K\}, \quad Y \in \{0, 1\}$$

where $B$ is a bag of $K$ instances, and $Y$ is the bag-level label.

The **standard MIL assumption** states:

- A bag is **positive** ($Y = 1$) if it contains **at least one** positive instance
- A bag is **negative** ($Y = 0$) if **all** instances are negative

Think of it like a keychain: if at least one key on the ring opens the door, the keychain is "positive." You don't know *which* key works — you just know the keychain as a whole either works or doesn't.

## Why Does MIL Matter?

MIL isn't just a theoretical curiosity — it's the natural formulation for many real-world problems where instance-level labels are expensive, ambiguous, or impossible to obtain.

### Computational Pathology

This is where I first encountered MIL during my M.S. at Tufts, working with [Michael Hughes](https://www.michaelchughes.com/) on deep multiple instance learning for computational pathology.

A whole-slide image (WSI) in digital pathology can be **100,000 × 100,000 pixels** — far too large for any neural network to process at once. The standard approach:

1. **Tile** the WSI into patches (e.g., 256×256 pixels)
2. Each patch is an **instance**
3. The collection of all patches from one slide is a **bag**
4. The slide-level diagnosis (cancer vs. no cancer) is the **bag label**

A pathologist labels the slide, not every individual patch. MIL learns which patches are diagnostic from slide-level labels alone.

### Other Applications

- **Drug discovery**: A molecule (bag) is a collection of conformations (instances). The molecule is active if at least one conformation binds.
- **Text classification**: A document (bag) is a collection of paragraphs (instances). The document is positive if at least one paragraph contains the relevant topic.
- **Image classification**: An image (bag) is a set of regions (instances). The image is positive if at least one region contains the object of interest.

## The MIL Framework

### Instance-Level vs. Bag-Level Approaches

There are two fundamental approaches to MIL:

**Instance-level methods** try to classify each instance individually, then aggregate predictions:

$$\hat{Y} = \max_{k=1}^{K} f(x_k)$$

This is the "max-pooling" approach — predict each instance, take the max as the bag prediction. Simple, but it throws away information about how instances relate to each other.

**Bag-level (embedding) methods** learn a representation for the entire bag, then classify at the bag level:

$$\hat{Y} = g\left(\text{AGGREGATE}(f(x_1), f(x_2), \ldots, f(x_K))\right)$$

where $f$ is an instance encoder and $g$ is a bag classifier. The key question is: **what aggregation function should we use?**

### Common Aggregation Functions

| Method | Aggregation | Pros | Cons |
|--------|------------|------|------|
| Max pooling | $\max_k h_k$ | Simple, respects MIL assumption | Ignores all but one instance |
| Mean pooling | $\frac{1}{K}\sum_k h_k$ | Uses all instances | Dilutes signal from rare positive instances |
| Attention | $\sum_k a_k h_k$ | Learns instance importance | More parameters, harder to train |

<div id="mil-interactive-demo" class="mil-demo-container"></div>

**Try it yourself** — drag the instances to see how their positions affect the **mean-pooled** bag embeddings (◆) and the decision boundary. Notice how dragging a positive instance (red) toward the negative cluster pulls the bag mean with it until mean pooling fails to separate the bags.

## A Simple MIL Model in PyTorch

Let's implement a basic MIL model with mean pooling:

```python
import torch
import torch.nn as nn

class SimpleMIL(nn.Module):
    def __init__(self, input_dim, hidden_dim=128):
        super(SimpleMIL, self).__init__()
        # Instance-level feature extractor
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )
        # Bag-level classifier
        self.classifier = nn.Sequential(
            nn.Linear(hidden_dim, 1),
            nn.Sigmoid(),
        )

    def forward(self, bag):
        # bag shape: (K, input_dim) where K = number of instances
        h = self.encoder(bag)       # (K, hidden_dim)
        z = h.mean(dim=0)           # (hidden_dim,) — mean pooling
        y = self.classifier(z)      # (1,)
        return y
```

This model:
1. Encodes each instance independently through a shared MLP
2. Aggregates instance embeddings via mean pooling
3. Classifies the aggregated bag representation

### Training Loop

```python
model = SimpleMIL(input_dim=512)
criterion = nn.BCELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

for epoch in range(100):
    for bag, label in dataloader:
        optimizer.zero_grad()
        pred = model(bag)
        loss = criterion(pred, label)
        loss.backward()
        optimizer.step()
```

## The Problem with Simple Pooling

Mean pooling treats every instance equally — a cancerous patch contributes the same as background tissue. Max pooling only looks at the single most extreme instance. Neither is ideal.

What if the model could learn to **pay attention** to the instances that matter?

This is exactly what **attention-based MIL** does, and it's the subject of the next post in this series.

## What's Next

This is the first post in the **Deep Dive: Multiple Instance Learning** series. Coming up:

1. **This post** — What is MIL and why it matters
2. **Attention-Based MIL** — The Ilse et al. (2018) architecture that changed the field
3. **Transformer MIL** — How self-attention and transformers are pushing MIL forward
4. **MIL in Practice** — Lessons learned from real-world computational pathology

## Additional Resources

- [Attention-Based Deep Multiple Instance Learning (Ilse et al., 2018)](https://arxiv.org/abs/1802.04712) — The foundational attention MIL paper
- [TorchMIL](https://github.com/Franblueee/torchmil) — A PyTorch library for MIL (I'm a contributor)
- [CLAM: Data-efficient and weakly supervised computational pathology](https://arxiv.org/abs/2004.09666) — Widely used MIL framework for pathology
- [Multiple Instance Learning: A Survey (Carbonneau et al.)](https://arxiv.org/abs/1612.03365) — Comprehensive MIL review
