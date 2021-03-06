import shutil
import tempfile
import unittest

import numpy as np
from pymc3 import summary
from sklearn.model_selection import train_test_split

from ps_toolkit.exc import PSToolkitError
from ps_toolkit import HLM


class HLMTestCase(unittest.TestCase):
    def setUp(self):
        def numpy_invlogit(x):
            return 1 / (1 + np.exp(-x))

        self.num_cats = 3
        self.num_pred = 1
        self.num_samples_per_cat = 100000

        self.alphas = np.random.randn(self.num_cats)
        self.betas = np.random.randn(self.num_cats, self.num_pred)
        #TODO: make this more efficient; right now, it's very explicit so I understand it.
        x_a = np.random.randn(self.num_samples_per_cat, self.num_pred)
        y_a = np.random.binomial(1, numpy_invlogit(self.alphas[0] + np.sum(self.betas[0] * x_a, 1)))
        x_b = np.random.randn(self.num_samples_per_cat, self.num_pred)
        y_b = np.random.binomial(1, numpy_invlogit(self.alphas[1] + np.sum(self.betas[1] * x_b, 1)))
        x_c = np.random.randn(self.num_samples_per_cat, self.num_pred)
        y_c = np.random.binomial(1, numpy_invlogit(self.alphas[2] + np.sum(self.betas[2] * x_c, 1)))

        X = np.concatenate([x_a, x_b, x_c])
        Y = np.concatenate([y_a, y_b, y_c])
        cats = np.concatenate([
            np.zeros(self.num_samples_per_cat, dtype=np.int),
            np.ones(self.num_samples_per_cat, dtype=np.int),
            2*np.ones(self.num_samples_per_cat, dtype=np.int)
        ])

        self.X_train, self.X_test, self.cat_train, self.cat_test, self.Y_train, self.Y_test = train_test_split(
            X, cats, Y, test_size=0.4
        )

        self.test_HLM = HLM()

        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)


class HLMFitTestCase(HLMTestCase):
    def test_fit_returns_correct_model(self):
        # Note: print is here so PyMC3 output won't overwrite the test name
        print("")
        self.test_HLM.fit(self.X_train, self.cat_train, self.Y_train)

        self.assertEqual(self.num_cats, self.test_HLM.num_cats)
        self.assertEqual(self.num_pred, self.test_HLM.num_pred)
        #TODO: Think about whether this is the right testing tolerance
        np.testing.assert_almost_equal(self.alphas, self.test_HLM.v_params.means['alpha'], decimal=1)
        np.testing.assert_almost_equal(self.betas, self.test_HLM.v_params.means['beta'], decimal=1)


class HLMPredictProbaTestCase(HLMTestCase):
    def test_predict_proba_returns_probabilities(self):
        print("")
        self.test_HLM.fit(self.X_train, self.cat_train, self.Y_train)
        probs = self.test_HLM.predict_proba(self.X_test, self.cat_test)
        self.assertEqual(probs.shape, self.Y_test.shape)

    def test_predict_proba_raises_error_if_not_fit(self):
        with self.assertRaises(PSToolkitError) as no_fit_error:
            test_HLM = HLM()
            test_HLM.predict_proba(self.X_train, self.cat_train)

        expected = "Run fit on the model before predict."
        self.assertEqual(str(no_fit_error.exception), expected)


class HLMPredictTestCase(HLMTestCase):
    def test_predict_returns_predictions(self):
        print("")
        self.test_HLM.fit(self.X_train, self.cat_train, self.Y_train)
        preds = self.test_HLM.predict(self.X_test, self.cat_test)
        self.assertEqual(preds.shape, self.Y_test.shape)


class HLMScoreTestCase(HLMTestCase):
    def test_score_scores(self):
        print("")
        self.test_HLM.fit(self.X_train, self.cat_train, self.Y_train)
        score = self.test_HLM.score(self.X_test, self.cat_test, self.Y_test)
        naive_score = np.mean(self.Y_test)
        self.assertGreaterEqual(score, naive_score)


class HLMSaveandLoadTestCase(HLMTestCase):
    def test_save_and_load_work_correctly(self):
        print("")
        self.test_HLM.fit(self.X_train, self.cat_train, self.Y_train)
        probs1 = self.test_HLM.predict_proba(self.X_test, self.cat_test)
        probs2 = self.test_HLM.predict_proba(self.X_test, self.cat_test)
        self.test_HLM.save(self.test_dir)

        HLM2 = HLM()

        HLM2.load(self.test_dir)

        self.assertEqual(self.test_HLM.num_cats, HLM2.num_cats)
        self.assertEqual(self.test_HLM.num_pred, HLM2.num_pred)
        self.assertEqual(summary(self.test_HLM.advi_trace), summary(HLM2.advi_trace))

        for key in self.test_HLM.v_params.means.keys():
            np.testing.assert_equal(self.test_HLM.v_params.means[key], HLM2.v_params.means[key])

        probs3 = HLM2.predict_proba(self.X_test, self.cat_test)

        np.testing.assert_almost_equal(probs3, probs1, decimal=1)
