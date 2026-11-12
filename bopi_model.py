"""Models are fixed before holdout evaluation; compare, do not select on test."""
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder,StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score,brier_score_loss,log_loss
from xgboost import XGBClassifier
from features import NUMERIC,CATEGORICAL
def preprocess(numeric=NUMERIC,categorical=CATEGORICAL):
    return ColumnTransformer([('num',make_pipeline(SimpleImputer(strategy='median'),StandardScaler()),numeric),('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),categorical)])
def model(cfg,kind='logistic',numeric=NUMERIC,categorical=CATEGORICAL):
    m=LogisticRegression(max_iter=cfg['logistic_max_iter'],random_state=cfg['seed']) if kind=='logistic' else XGBClassifier(n_estimators=cfg['max_iter'],max_depth=cfg['xgb_depth'],learning_rate=cfg['xgb_learning_rate'],subsample=1.,colsample_bytree=1.,n_jobs=2,random_state=cfg['seed'],eval_metric='logloss')
    return make_pipeline(preprocess(numeric,categorical),m)
def target(df,kind='boundary'):
    return df.boundary if kind=='boundary' else ((df.charged>=2)|(df.wides>0)|(df.noballs>0)).astype(int)
def metrics(y,p):
    return {'auc':float(roc_auc_score(y,p)) if len(set(y))>1 else None,'brier':float(brier_score_loss(y,p)),'logloss':float(log_loss(y,p,labels=[0,1])),'n':len(y)}
