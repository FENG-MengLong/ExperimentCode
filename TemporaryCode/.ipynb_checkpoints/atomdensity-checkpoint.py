#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Jan 13 13:13:26 2025

@author: apple
"""

import numpy as np
import cv2
import matplotlib.pyplot as plt


def read_asc_file(file_path):
    data = []
    with open(file_path, 'r') as file:
        for line in file:
            # Skip empty lines or metadata
            if line.strip() and not line.startswith("#"):
                row = list(map(float, line.split()))
                data.append(row)
    return np.array(data)


def crop_data(data, top_left, bottom_right):
    y1, x1 = top_left
    y2, x2 = bottom_right
    return data[y1:y2, x1:x2]




atomdata = read_asc_file("/Users/apple/Desktop/GradCourse/research/shadow image/test03/atoms-1.asc")
noatomdata = read_asc_file("/Users/apple/Desktop/GradCourse/research/shadow image/test03/no-atoms.asc")
noatomnolightdata = read_asc_file("/Users/apple/Desktop/GradCourse/research/shadow image/test03/bg.asc")


atomnumbernom = atomdata - noatomnolightdata

atomnumberde = noatomdata-noatomnolightdata

crosssection = -2.91E-9 #cm^2

pixelsize = 6.45E-4 #cm

pixelarea = pixelsize**2




condition = (atomnumbernom/atomnumberde > 0) & (atomnumberde != 0) & (atomnumbernom/atomnumberde <1)


ratio = np.zeros_like(atomdata, dtype=float)  # Initialize the ratio array with zeros

#ratio[condition] = atomnumbernom[condition] / atomnumberde[condition] # Apply the ratio where condition is true


ratio[condition] = np.log(atomnumbernom[condition] / atomnumberde[condition]) / crosssection  # Apply the ratio where condition is true


crop_top_left = (260, 650)  # (row, column) of top-left corner
crop_bottom_right = (500, 900)  # (row, column) of bottom-right corner
atomdensity_crop = crop_data(ratio, crop_top_left, crop_bottom_right)

atomdensity_total = np.sum(atomdensity_crop) * pixelarea /10**6




