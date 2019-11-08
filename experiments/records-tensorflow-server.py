
# coding: utf-8

# In[1]:
from __future__ import division

import json
import os
import tarfile
import time
from collections import Counter

import matplotlib.pyplot as plt
import numpy as np
import requests
import sklearn
from sklearn import metrics
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import make_scorer
from sklearn.model_selection import GridSearchCV, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

import tensorflow as tf

# In[2]:

with open("./data/zenodo_open_metadata_06_04_2017_cleaned_20_08_17.json", "r") as fp:
    data = json.load(fp)
labels = [d['spam'] for d in data]


# In[3]:

def feat_tr(d):
    return d['description'] + d['title']

X = [feat_tr(d) for d in data]
y = np.array([[1 if d['spam'] else 0, 1 if not d['spam'] else 0] for d in data])

ngram_range=(1, 1)
count_vect = CountVectorizer(ngram_range=ngram_range, max_features=15000)
tfid = TfidfTransformer()
X_v = count_vect.fit_transform(X)
X_v = tfid.fit_transform(X_v)


# In[4]:

#trainX, testX, trainY, testY = train_test_split(X_v, np.asarray(y, dtype=np.float32), test_size=3000, train_size=6000, random_state=42)

trainX, testX, trainY, testY = train_test_split(X_v, np.asarray(y, dtype=np.float32), test_size=0.25, random_state=40)


# In[5]:

trainX = np.asarray(trainX.todense(), dtype=np.float32)
#trainY = trainY
testX = np.asarray(testX.todense(), dtype=np.float32)
#testY = testY


# In[6]:

numFeatures = trainX.shape[1]
numLabels = trainY.shape[1]
numEpochs = 27000
# a smarter learning rate for gradientOptimizer
learningRate = tf.train.exponential_decay(learning_rate=0.0008,
                                          global_step= 1,
                                          decay_steps=trainX.shape[0],
                                          decay_rate= 0.95,
                                          staircase=True)


# In[7]:

# X = X-matrix / feature-matrix / data-matrix... It's a tensor to hold our email
# data. 'None' here means that we can hold any number of emails
Xtens = tf.placeholder(tf.float32, [None, numFeatures])
# yGold = Y-matrix / label-matrix / labels... This will be our correct answers
# matrix. Every row has either [1,0] for SPAM or [0,1] for HAM. 'None' here 
# means that we can hold any number of emails
yGold = tf.placeholder(tf.float32, [None, numLabels])


# In[8]:

# Values are randomly sampled from a Gaussian with a standard deviation of:
#     sqrt(6 / (numInputNodes + numOutputNodes + 1))

weights = tf.Variable(tf.random_normal([numFeatures,numLabels],
                                       mean=0,
                                       stddev=(np.sqrt(6/numFeatures+
                                                         numLabels+1)),
                                       name="weights"))

bias = tf.Variable(tf.random_normal([1,numLabels],
                                    mean=0,
                                    stddev=(np.sqrt(6/numFeatures+numLabels+1)),
                                    name="bias"))


# In[9]:

# INITIALIZE our weights and biases
init_OP = tf.initialize_all_variables()

# PREDICTION ALGORITHM i.e. FEEDFORWARD ALGORITHM
apply_weights_OP = tf.matmul(Xtens, weights, name="apply_weights")
add_bias_OP = tf.add(apply_weights_OP, bias, name="add_bias") 
activation_OP = tf.nn.sigmoid(add_bias_OP, name="activation")


# In[10]:

cost_OP = tf.nn.l2_loss(activation_OP-yGold, name="squared_error_cost")


# In[11]:

training_OP = tf.train.GradientDescentOptimizer(learningRate).minimize(cost_OP)


# In[13]:

# Create a tensorflow session
sess = tf.Session()

# Initialize all tensorflow variables
sess.run(init_OP)

## Ops for vizualization
# argmax(activation_OP, 1) gives the label our model thought was most likely
# argmax(yGold, 1) is the correct label
correct_predictions_OP = tf.equal(tf.argmax(activation_OP,1),tf.argmax(yGold,1))
# False is 0 and True is 1, what was our average?
accuracy_OP = tf.reduce_mean(tf.cast(correct_predictions_OP, "float"))
# Summary op for regression output
activation_summary_OP = tf.summary.histogram("output", activation_OP)
# Summary op for accuracy
accuracy_summary_OP = tf.summary.scalar("accuracy", accuracy_OP)
# Summary op for cost
cost_summary_OP = tf.summary.scalar("cost", cost_OP)
# Summary ops to check how variables (W, b) are updating after each iteration
weightSummary = tf.summary.histogram("weights", weights.eval(session=sess))
biasSummary = tf.summary.histogram("biases", bias.eval(session=sess))
# Merge all summaries
all_summary_OPS = tf.summary.merge_all()
# Summary writer
writer = tf.summary.FileWriter("summary_logs", sess.graph)

# Initialize reporting variables
cost = 0
diff = 1

# Training epochs
for i in range(numEpochs):
    if i > 1 and diff < .0001:
        print("change in cost %g; convergence."%diff)
        break
    else:
        # Run training step
        step = sess.run(training_OP, feed_dict={Xtens: trainX, yGold: trainY})
        # Report occasional stats
        if i % 10 == 0:
            # Add epoch to epoch_values
            #epoch_values.append(i)
            # Generate accuracy stats on test data
            summary_results, train_accuracy, newCost = sess.run(
                [all_summary_OPS, accuracy_OP, cost_OP], 
                feed_dict={Xtens: trainX, yGold: trainY}
            )
            # Add accuracy to live graphing variable
            #accuracy_values.append(train_accuracy)
            # Add cost to live graphing variable
            #cost_values.append(newCost)
            # Write summary stats to writer
            writer.add_summary(summary_results, i)
            # Re-assign values for variables
            diff = abs(newCost - cost)
            cost = newCost

            #generate print statements
            print("step %d, training accuracy %g"%(i, train_accuracy))
            print("step %d, cost %g"%(i, newCost))
            print("step %d, change in cost %g"%(i, diff))

            y_res = sess.run(activation_OP, feed_dict={Xtens:testX})
            y_res = list(y_res[:,0] > 0.5)
            y_gold = list(bool(yy) for yy in testY[:,0])
            acc = [(ref, pred) for ref, pred in zip(y_gold, y_res)]
            c = Counter(acc)
            print(c)
            print("S->S:{0:.5f}   H->H:{1:.5f}   Acc:{2:.5f}".format(
                c[(True, True)] / (c[(True, True)] + c[(True, False)]),
                c[(False, False)] / (c[(False, False)] + c[(False, True)]),
                (c[(False, False)] + c[(True, True)]) / (len(acc))
            ))
            if i % 500 == 0:
                saver = tf.train.Saver()
                saver.save(sess, "sessions/model_epoch_{0}.ckpt".format(i))

print("final test set: %s" %str(sess.run(accuracy_OP,
                                        feed_dict={Xtens: testX,
                                                   yGold: testY})))

saver = tf.train.Saver()
saver.save(sess, "sessions/model_final.ckpt")

# Close tensorflow session
#sess.close()
