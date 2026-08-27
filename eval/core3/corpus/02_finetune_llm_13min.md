---
title: Fine-tune your own LLM in 13 minutes, here’s how
channel: David Ondrej
url: "https://www.youtube.com/watch?v=g80Q1sVtikE"
cover: imgs/cover.jpg
description: "Learn about the best AI Business models here - https://www.youtube.com/watch?v=Ta5g-OxjPO4"
language: en
---

# Fine-tune your own LLM in 13 minutes, here’s how

Learn about the best AI Business models here - https://www.youtube.com/watch?v=Ta5g-OxjPO4

Here is how to fine-tune your own AI model step by step. So, what even is fine-tuning? Fine-tuning is adjusting a base model's weights to improve the model's performance on certain specific tasks. Thanks to fine-tuning, very small AI models can outperform even the best models of today like GBD5. So, in this video, I'll show you how to fine-tune your first AI model from scratch. [00:00:00 → 00:00:25]

And it's actually easier than you think. Now, believe it or not, fine-tuning models is actually a massive startup opportunity. Why combinator themselves are actively begging founders to launch startups around fine-tuned models. It's literally one of their top 20 requested categories. And that's because the problem with most AI startups is that they are easily replaceable. [00:00:25 → 00:00:44]

They don't have any new technology, which means that sooner or later, OpenAI will try to replace you, and we've seen this with the recent dev day. So creating your own fine-tuned models gives you a real mode that gives you an opportunity to create a lasting business that can earn monopoly profits. Now before you can finetune, you need to choose a model. OpenAI recently released two new open source models. GPD OSS 12B and GPDoss 20B. [00:00:44 → 00:01:08]

Now what makes the GPDoss models ideal for fine-tuning is that they are both really really good and they are small enough to run locally. So, we can take GPOSS and fine-tune the weights of it to create our own powerful model for any use case you want. However, there's a problem. Most people struggle with finding highquality data sets to fine-tune your model on. And without a data set, you cannot begin fine-tuning. [00:01:08 → 00:01:34]

So, later in the video, I'll show you how to solve this problem. Another major benefit of fine-tuning is uncensored models. This is how every single uncensored model gets created, aka a model that can answer anything, even the most controversial of questions. Now, uncensored models are becoming more and more important since companies and governments seem to not stop with the levels of propaganda they put out there. And so, while the average person is talking to biased LLMs, we're going to fine-tune our own model with our own best interests in mind. [00:01:32 → 00:02:02]

Also, learning how to fine-tune is a great way to differentiate yourself. If you are serious about AI, this is simply a must-have skill. Whether that's for your personal life, your career, your business, fine-tuning is the future. So now let me show you how to fine-tune your own GPT model from scratch. And no, you don't have to be a programmer to do this. [00:02:02 → 00:02:21]

All right. So we're going to be using Unsllo, which is a open source library to fine-tune any models. I mean, they support all kinds of different models. GPTOSS, Gemmaen, Quenfree, 54, Mistrol, Lamaree. So feel free to choose whatever you want, but I'm going to go with the GPTOSS 20B. [00:02:21 → 00:02:37]

So click on the free notebook. Oh, and by the way, I'm going to link the GitHub below the video. Once you click start for free, you'll get redirected to Google Collab, which is a Jupyter notebook hosted by Google, where you get free GPUs. It's literally a free graphics card to run this Python code for you, which allows us to fine-tune any model, at least any open source model. So, the first thing we have to do is go to the top right and click on connect. [00:02:37 → 00:03:00]

This will connect you to the runtime using one of their Tesla T4 GPUs. And boom, once you see the RAM and disk, you know that you have been connected successfully. Beautiful. All right. So let's start with the installation which is this first block. [00:03:00 → 00:03:14]

So let's run it. This will install the necessary dependencies for ansllo and for fine-tuning of this model. We can see that numpy is one of them. Transformers is another. But the main thing is torch which stands for pytorch which is a deep learning framework from meta. [00:03:13 → 00:03:26]

It's actually one of the most popular ways to make AI models. All right. The first cell has completed. Let's go to the next one. And here we choose which model we want to fine-tune using the anselof library. [00:03:26 → 00:03:38]

So, as you can see, this one is set to GPD OSS 20B. You can also set the max sequence length or whether you want 4bit quantization, but honestly, you should just leave all of these to default because the guys at Anslov know way more about fine-tuning than me or you. So, let's scroll back up and let's run this cell. This will begin downloading the model, which we can see right here. Since this model is pretty small, 20 billion parameters, it's only a couple of gigabytes. [00:03:38 → 00:04:01]

So, this actually is not the finetuning process yet. It's just Anselof pulling the model and optimizing our environment for faster fine-tuning later on. Okay, the cell has finally finished. Let's go to the next one. Okay, so let's run the next cell. [00:04:01 → 00:04:14]

This one adds Laura adapters, which to be honest, I don't fully understand. And so I asked Veal what this cell does, and it explained to me. And I used one of the built-in keyboard shortcuts to make the message simpler and shorter. This is just one of many reasons why you should use vectal over chat GBT over perplexity or overcloth. You can create your own custom slash commands to prevent yourself from running the same prompts over and over. [00:04:12 → 00:04:35]

Plus, you can use all of the latest and greatest AI models in a single app. So, go to vector. ai and give it a shot. So, we know that this cell, what it does is it adds lura adapters to the model. So, only a smart part of it, small part of the parameters actually get fine-tuned. [00:04:35 → 00:04:50]

So, the next part is the reasoning effort. And to be honest, we can completely skip this. It's not needed to run it. It works without it. So let's just collapse that and go into the data prep. [00:04:50 → 00:05:00]

This is where having your own data set comes into place. Now this collab already includes a default data set which is this one hugging face H4 multilingual thinking. And this is a reasoning data set where the chain of fault has been translated from English into four other languages Spanish and German. Abada data set is neat good and that's why we're going to use this one agent. Now this data set was made to turn LLMs into more of agents right teach them agentic behavior. [00:05:00 → 00:05:32]

So it's focused on reasoning planning and tool calling. So here's an example conversation where we have ro user then some content assistant response another instructions from the user and this is I think buying something on the internet and we have assistant user. So this will be fine-tuning the model to know how to navigate the web. So if you want to build your own version of OpenAI operator or the OpenAI agent mode, a data set like this would be absolutely necessary. In fact, it's very likely that OpenAI use data sets like this to fine-tune those models. [00:05:32 → 00:06:02]

So what we need to do in this data prep part is we need to replace this default multilingual thinking with our actual data set. So let's click on the copy button right here to copy the name. Let's switch back to Google Collab. Replace this and paste in this name. And then we can run this cell. [00:06:02 → 00:06:19]

Now the problem is that if you just run it like this you will get an error and that's because this data set includes multiple files. So inside of hacking face you can actually see files and versions. Then if you navigate into data you can see that there's multiple JSON L files. We need to specify which one we want to train on. All right. [00:06:19 → 00:06:38]

So let me actually debug this with vectors. So I paste in the whole error. Okay. So this is actually the working pattern here. We need to just load one file because this data set has a different schema than this one. [00:06:38 → 00:06:49]

So, this wasted a bunch of my time. So, just don't make the same mistake. Um, yeah, here is the correct way to handle that. Let's run that. And boom, we finally succeeded without errors. [00:06:49 → 00:06:59]

So, yeah, let's continue with the model training. The next cell applies the chat templates standardized share GBD prompt, which actually I do want to find what that is. So, I guess this is a sllo's system prompt. Okay. What standardized share GBT does is a data format converter from from enslave that transform conversation data sets. [00:06:59 → 00:07:22]

Okay. So this is what share GB format looks like from human say hello from GPD hi there. This is chat ML format. Okay. So it basically just replaces human with user and assistant. [00:07:20 → 00:07:32]

Yeah. GPT models have been trained on this user assistant conversations for a while like since I don't know since GPD1 GPD2. So this is a convention that OpenAI uses. Okay, so this cell was super fast. Next, let's look at what the data set looks like actually. [00:07:32 → 00:07:48]

So, it starts off with the system prompt. You are CH GBD, a large language model trained by OpenAI. And the system prompt ends here. So, it just tells you the reasoning, the current date, knowledge cut off, reasoning effort, and the valid channels. And then we start the user message. [00:07:48 → 00:08:03]

You are web shopping. I'll give you instructions what to do. And yeah, this is our data set. Nice. What is unique about GPDOSS that it uses OpenAI harmony and this is actually a new response format from OpenAI for the GPD OSS models. [00:08:03 → 00:08:17]

This format enables the model to output multiple different channels for chain of thought and tool calling preamles along with regular responses. Interesting. So this is basically a new prompt engineering format, right? If you want me to make a video where I dive deeper into OpenAI harmony and the implications for prompt engineering and context engineering, comment below because this has released just two months ago and somehow I haven't seen it before. Now the next cell is actually the first step of the training of the model. [00:08:17 → 00:08:47]

So this is the most exciting part. This is where the fine tuning begins. So here we have control over all of these different parameters. I'm just going to tweak the learning rate, but everything else should be good. We do 60 steps to speed things up. [00:08:47 → 00:09:01]

Okay. But yeah, if you want to do a full run, a full training run, which means, you know, once you're happy with the data set, once you're happy with all the settings, you would uncomment this out and you would do full run. Keep in mind that we're running the cheapest T4 Tesla GPU. So, this one is completely free. It's actually, yeah, it's the cheapest. [00:09:01 → 00:09:18]

It's the free. Google gives it for free. If you have the paid version of Google Collab, you get access to more powerful GPU. So, if you go into runtime, you can click on change runtime type. And we can see that there's A100, which is like the third or fourth oldest generation of Nvidia GPUs. [00:09:16 → 00:09:32]

It's not H100s or H200s, but it's still a very strong GPU. Like on eBay, this still goes for like $10,000 or something. Or we can use the V6 TPUs from Google. So this is, you know, their tensor processing unit, Google's own chip basically. But these are only available on the paid Google Collab. [00:09:32 → 00:09:50]

But if you were to do a full training run, you probably should switch to faster GPU. Otherwise, you would be sitting there for a very long time. All right, so let's run this cell. It doesn't take that much time, actually. But the next cell, this one is dangerous. [00:09:50 → 00:10:01]

This was causing issues during training. So, I'm just going to comment it out. Uh I'm not sure why, but hey, just to save you guys time, so you don't have to repeat the same mistakes. Now, we can probably skip some of these because this is just showing the memory stats like which GPU we're using and how much memory we have. But this is the important part where we actually start a training run. [00:10:01 → 00:10:21]

So, let's run it. And this could take anywhere from five to 15 minutes depending how lucky you get with the GPU and the size of your data set and how many uh steps and epochs you selected. So after it finishes running you can see how long it took right so in this case it was 10 minutes 11 minutes basically and what percentage was used at its peak. But the fun part is the inference. Now, if you don't understand what inference means, this is basically when you run the model, right? [00:10:21 → 00:10:50]

Training is when you either create a model from scratch or where you fine-tune a existing model, which is what we did right here. Inference is what you do when you're chatting inside of vect, inside of JGBT when you're actually chatting with the completed model, right? The model is already finished. It's no longer training. You're just using it to answer your questions. [00:10:50 → 00:11:09]

This is inference. So here in the collab, after your model finishes training, you can chat with it to see how it responds differently than the base model. Now, by the way, since this base model is super small, you can literally get it on Olama GPT OSS. If you have a good computer, especially like a high-end MacBook or a Mac Studio, you can run the 120B. If you didn't spend at least 5K USD on your computer, you probably cannot run the 12B, but you definitely can run the 20B, right? [00:11:09 → 00:11:36]

Unless your laptop is like 20 years old. uh then you probably can't run either. But if you want to compare how your fine-tuned version of GPOSS responds versus the default GPOSS, you can just download it locally so that you can run the inference on your laptop, which is by the way also completely private. That's another benefit. And then you see how the default GPOSS responds versus your finetuned one. [00:11:36 → 00:12:01]

Now to save it, you have two options. You can either save it locally so that you have it on your computer or you can push you can do model. push push to hop which saves the model on hugging face. So then you need to uncomment this line. Boom. [00:12:01 → 00:12:15]

You need to comment this one. And here you need to replace this with your hugging face username and the name of the model that you want plus with your hugging face secret token which do not share that with anybody. And if you do go with the hugging face route, you can then use it here. But you need to replace the model name again with your hugging face name. So whatever you save it as, put it here. [00:12:13 → 00:12:34]

And yeah, you can either chat with it here, which is not really convenient, or you can use a hugging face model to build a full stack web app, which is an entire video on its own. So if you do want to see more videos on fine-tuning, on hugging face, how to build data sets for finetuning, how to create synthetic data, make sure to subscribe. If I see a lot of people subscribing from this video, that would be a very strong signal that I should make more content like this one. With that being said, shout out to Anseloff for creating this Google Collab and for building such an amazing open source library. And yeah, hopefully you guys enjoy this video and I wish you a wonderful productive week. [00:12:34 → 00:13:09]

See you. [00:13:09 → 00:13:10]
