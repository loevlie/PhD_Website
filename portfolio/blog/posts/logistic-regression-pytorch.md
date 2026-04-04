---
title: "Logistic Regression with PyTorch"
date: 2021-10-04
updated: 2024-01-04
author: "Dennis Loevlie"
tags: ["PyTorch", "Machine Learning", "Logistic Regression", "Python"]
excerpt: "A introduction to applying logistic regression for binary classification using PyTorch."
image: "portfolio/images/blog/lr-cover.jpeg"
medium_url: "https://medium.com/data-science/logistic-regression-with-pytorch-3c8bbea594be"
---

Binary logistic regression is used to classify two linearly separable groups. This linearly separable assumption makes logistic regression extremely fast and powerful for simple ML tasks. An example of linearly separable data that we will be performing logistic regression on is shown below:

![Linearly Separable Data](/static/portfolio/images/blog/lr-data.png)

Here the linearly separable groups are:

1. Red = 0
2. Blue = 1

We want to use logistic regression to map any $[x_1, x_2]$ pair to the corresponding class (red or blue).

<div id="lr-interactive-demo" class="lr-demo-container"></div>

**Try it yourself** — drag the dots above to see when a linear decision boundary can (and can't) separate two classes.

## Step 1: Splitting our dataset into a train/test split

We do this so we can evaluate our models performance on data it didn't see during training. Usually, if you tell someone your model is 97% accurate, it is assumed you are talking about the validation/testing accuracy.

You can do this yourself pretty easily, but honestly, the `sklearn.train_test_split` function is really nice to use for readability.

```python
X_train, X_test, y_train, y_test = train_test_split(
    inputs, labels, test_size=0.33, random_state=42
)
```

## Step 2: Building the PyTorch Model Class

We can create the logistic regression model with the following code:

```python
import torch

class LogisticRegression(torch.nn.Module):
    def __init__(self, input_dim, output_dim):
        super(LogisticRegression, self).__init__()
        self.linear = torch.nn.Linear(input_dim, output_dim)

    def forward(self, x):
        outputs = torch.sigmoid(self.linear(x))
        return outputs
```

In our "forward" pass of the PyTorch neural network (really just a perceptron), the visual representation and corresponding equations are shown below:

![Neural Network Architecture](/static/portfolio/images/blog/lr-nn-arch.png)

The sigmoid function is extremely useful for two main reasons:

1. It transforms our linear regression output to a probability from 0 to 1. We can then take any probability greater than 0.5 as being 1 and below as being 0.
2. Unlike a stepwise function (which would transform the data into the binary case as well), the sigmoid is differentiable, which is necessary for optimizing the parameters using gradient descent (we will show later).

$$\sigma(z) = \frac{1}{1 + e^{-z}}$$

![Sigmoid Function with Decision Boundary](/static/portfolio/images/blog/lr-sigmoid.png)

## Step 3: Initializing the Model

Also, we should assign some hyper-parameters:

```python
epochs = 200000
input_dim = 2       # Two inputs x1 and x2
output_dim = 1      # Single binary output
learning_rate = 0.01

model = LogisticRegression(input_dim, output_dim)
```

- **Epoch** — Indicates the number of passes through the entire training dataset the network has completed.
- **learning_rate** — A tuning parameter in an optimization algorithm that determines the step size at each iteration while moving toward a minimum of a loss function. High learning rate means you might never be able to reach a minimum. Low learning rate will take longer.

## Step 4: Initializing the Loss Function and the Optimizer

### Binary Cross Entropy Loss

```python
criterion = torch.nn.BCELoss()
```

$$\text{BCE} = -\frac{1}{m} \sum_{i=1}^{m} \left[ y_i \log(\hat{y}_i) + (1 - y_i) \log(1 - \hat{y}_i) \right]$$

- $m$ = Number of training examples
- $y$ = True y value
- $\hat{y}$ = Predicted y value

### Stochastic Gradient Descent

```python
optimizer = torch.optim.SGD(model.parameters(), lr=learning_rate)
```

There are a plethora of common NN optimizers but most are based on **Gradient Descent.** This optimization technique takes steps toward the minimum of the loss function with the direction dictated by the gradient of the loss function in terms of the weights and the magnitude or step size determined by the learning rate.

**Note:** To reach the loss function's minimum accurately and quickly, it is beneficial to slowly decrease your learning rate, and optimizers like Adaptive Movement Estimation algorithm (**ADAM**), which PyTorch has also implemented, do this for us. You can find out more about the PyTorch implementation of these optimizers at the [PyTorch optim docs](https://pytorch.org/docs/stable/optim.html).

We update the parameters to minimize the loss function with the following equations:

$$w = w - \alpha \frac{\partial L}{\partial w}$$

$$\beta = \beta - \alpha \frac{\partial L}{\partial \beta}$$

where $\alpha$ is the learning rate.

You might be wondering where we get the $\frac{\partial L}{\partial w}$ and $\frac{\partial L}{\partial \beta}$, and that would be a great question! In neural networks, we use back-propagation to get the partial derivatives. Luckily for us, in logistic regression the equations simplify. Using the chain rule we can deduce:

$$\frac{\partial L}{\partial w} = \frac{\partial L}{\partial \hat{y}} \cdot \frac{\partial \hat{y}}{\partial z} \cdot \frac{\partial z}{\partial w}$$

We can derive $\frac{\partial L}{\partial \beta}$ similarly. Luckily autograd helps do all of this for us!

## Step 5: Train the Model

First, we convert our inputs and labels from numpy arrays to tensors.

```python
X_train, X_test = torch.Tensor(X_train), torch.Tensor(X_test)
y_train, y_test = torch.Tensor(y_train), torch.Tensor(y_test)
```

Next, we build our training loop and store the losses. Every so often we can also print out the accuracy on the test data to see how our model is doing.

```python
losses = []
for epoch in range(epochs):
    optimizer.zero_grad()
    outputs = model(X_train)
    loss = criterion(outputs, y_train)
    loss.backward()
    optimizer.step()
    losses.append(loss.item())
```

![BCE Loss as a function of Epoch](/static/portfolio/images/blog/lr-loss.png)

## Step 6: Plotting the Results

Since we know the decision boundary would be $w \cdot x + b = 0$ we can plot the decision boundary. The results are below:

**Train:**

![Decision boundary on training data](/static/portfolio/images/blog/lr-train.png)

**Test:**

![Decision boundary on testing data](/static/portfolio/images/blog/lr-test.png)

## Step 7: How to get Predictions on New Data!

If you had a new point at x1=1, x2=1 visually (in 2-dimensional space), it's easy to tell that we should classify the point as "red". So let's check if our model is working correctly and show how to get a prediction from the model on new data:

```python
x1 = 1
x2 = 1
new_data = torch.tensor([x1, x2]).type(torch.FloatTensor)

with torch.no_grad():
    prediction = model(new_data).round()
    if prediction == 1.0:
        print(f'The model classifies this point as RED')
    else:
        print(f'The model classifies this point as BLUE')
```

The new point is plotted against the training data below:

![Predicting on New Data](/static/portfolio/images/blog/lr-predict.png)

```
>>> The model classifies this point as RED
```

## The full code

The full implementation is available as a [GitHub Gist](https://gist.github.com/loevlie/bf867387add01904dbcba6b78b25b606).

## Additional Resources

- [PyTorch Neural Network Documentation](https://pytorch.org/docs/stable/nn.html)
- [CMU Deep Learning Course (11-785)](https://deeplearning.cs.cmu.edu/F21/index.html)
- [PyTorch Autograd Explained](https://www.youtube.com/watch?v=MswxJw-8PvE&t=304s)
