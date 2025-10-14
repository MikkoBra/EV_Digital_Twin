from anomaly_detection import data_preprocessing

def inference(data, model, scaler, pca):
    # preprocess the data for the isolation forrest model
    data = data_preprocessing.preprocess_data(data, scaler, pca)

    # model inference
    pred = model.predict(data)[0]
    
    if pred == -1:
        is_anomaly = True
    else:
        is_anomaly = False
    
    # get the anomaly score from the model
    anomaly_score = model.decision_function(data)[0]

    return is_anomaly, anomaly_score