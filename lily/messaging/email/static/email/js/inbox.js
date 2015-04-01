(function ($, window, document, undefined) {
    var editor;

    window.HLInbox = {
        config: {
            accountDeactivatedMessage: 'Your account doesn\'t seem to be active. Please activate your account to view your email.',
            inboxCcInput: '.inbox-compose .mail-to .inbox-cc',
            inboxBccInput: '.inbox-compose .mail-to .inbox-bcc',
            singleMessageSelector: '.inbox-content .view-message',
            templateField: '#id_template',
            inboxComposeSubmit: '.inbox-compose [type="submit"]',
            wysiHtmlToolbar: '#wysihtml5-toolbar',
            replyButton: '.reply-btn',
            tagsAjaxSelector: '.tags-ajax',
            emailAccountInput: '#id_send_from',
            sendToNormalField: '#id_send_to_normal',
            overwriteTemplateConfirm: 'Selecting a different template will overwrite the text you\'ve typed. Do you want to load the template anyway?',
            emptyTemplateAttachmentRow: '#empty-template-attachment-row',
            templateAttachmentDeleteButton: '#template-attachments [data-formset-delete-button]',
            templateAttachmentUndoDeleteButton: '#template-attachments [data-formset-undo-delete]',
            templateAttachmentsDiv: '#template-attachments',
            templateAttachmentName: '.template-attachment-name',
            templateAttachmentIds: '#template-attachment-ids',
            templateAttachmentId: '.template-attachment-id',
            templateAttachmentRow: '.template-attachment-row'
        },

        init: function (config) {
            var self = this;

            // Setup config
            if (typeof (config === 'object')) {
                $.extend(this.config, config);
            }

            self.initListeners();
            Metronic.initUniform();
        },

        initListeners: function() {
            var self = this,
                cf = self.config;

            $('body')
                .on('click', cf.inboxCcInput, function() {
                    // Handle compose/reply cc input toggle
                    self.handleAdditionalRecipientsInput('cc');
                })
                .on('click', cf.inboxBccInput, function() {
                    // Handle compose/reply bcc input toggle
                    self.handleAdditionalRecipientsInput('bcc');
                })
                .on('change', cf.emailAccountInput, function () {
                    self.changeTemplateField.call(self, this, false);
                })
                .on('change', cf.templateField, function () {
                    self.changeTemplateField.call(self, this, true);
                })
                .on('change', cf.sendToNormalField, function () {
                    self.changeTemplateField.call(self, cf.templateField, false);
                })
                .on('click', cf.replyButton, function () {
                    // Open links when clicking the reply button
                    $('.inbox-view').hide();
                    $('.inbox-loading').show();
                })
                .on('click', cf.inboxComposeSubmit, function (event) {
                    self.handleInboxComposeSubmit(this, event);
                })
                .on('change', cf.tags, function () {
                    self.handleTagsAjaxChange(this);
                })
                .on('click', cf.templateAttachmentDeleteButton, function() {
                    var attachmentRow = $(this).closest('.form-group');
                    self.handleTemplateAttachmentsChange(attachmentRow);
                })
                .on('click', cf.templateAttachmentUndoDeleteButton, function() {
                    var attachmentRow = $(this).closest('.form-group');
                    self.handleTemplateAttachmentsChange(attachmentRow);
                });

                $('.inbox-compose input').on('keydown keyup keypress', function(event) {
                    // Make sure pressing enter doesn't do anything (except selecting something in a dropdown)
                    if (event.which == 13) {
                        event.preventDefault();
                    }
                });
        },

        customParser: function () {
            function parse(elementOrHtml, rules, context, cleanUp) {
                return elementOrHtml;
            }

            return parse;
        },

        initEmailCompose: function (emailComposeConfig) {
            var self = this;

            if (typeof (emailComposeConfig === 'object')) {
                $.extend(self.config, emailComposeConfig);
            }

            self.initWysihtml5();

            // If loadDefaultTemplate isn't set there was an error, so don't do any template loading
            if (self.config.loadDefaultTemplate !== null) {
                if (self.config.loadDefaultTemplate) {
                    // If no template was given in the url, load the default template
                    self.loadDefaultEmailTemplate();
                }
                else {
                    // Otherwise trigger change event so the given template gets loaded
                    $(self.config.templateField).val(self.config.template).change();
                }
            }

            if (self.config.recipient) {
                $(self.config.sendToNormalField).select2('data', self.config.recipient);
            }
        },

        initWysihtml5: function () {
            var self = this;

            editor = new wysihtml5.Editor('id_body_html', {
                toolbar: 'wysihtml5-toolbar',
                parser: self.customParser(),
                handleTables: false
            });

            // extra div is needed so the editor auto resizes
            editor.setValue('<div id="body-html-content">' + editor.getValue() + '</div>');

            editor.observe('load', function () {
                $(this.composer.element).on('keydown paste change focus blur', function () {
                    self.resizeEditor();
                });

                // Make the editor the correct height on load
                self.resizeEditor();
            });

            // Set heading properly after change
            var toolbar = $(self.config.wysiHtmlToolbar);
            $(toolbar).find('a[data-wysihtml5-command="formatBlock"]').click(function(e) {
                var target = e.target || e.srcElement;
                var el = $(target);
                $(toolbar).find('.current-font').text(el.html());
            });

            // Not putting this in the initListeners since it's only used in the email compose
            $(window).on('resize', function() {
                self.resizeEditor();
            });
        },

        resizeEditor: function () {
            $('.wysihtml5-sandbox')[0].style.height = editor.composer.element.scrollHeight + 'px';
        },

        handleAdditionalRecipientsInput: function (inputType) {
            var $ccLink = $('.inbox-compose .mail-to .inbox-' + inputType);
            var $inputField = $('.inbox-compose .input-' + inputType);
            $ccLink.hide();
            $inputField.show();
            $('.close', $inputField).click(function () {
                $inputField.hide();
                $ccLink.show();
                $inputField.find('.tags').select2('val', '');
            });
        },

        changeTemplateField: function (templateField, templateChanged) {
            var self = this;
            if (self.config.templateList) {
                var selectedTemplate = parseInt($(templateField).val());
                var subjectField = $('#id_subject');
                var subject = '';
                var recipientId = null;
                var emailAccountId = $(self.config.emailAccountInput).val();

                if (selectedTemplate) {
                    angular.forEach(self.config.templateList, function (value, key) {
                        if (value.id == selectedTemplate) {
                            subject = value.subject;
                        }
                    });

                    if (this.config.messageType === 'new' && subject != '') {
                        // Only overwrite the subject if a new email is being created
                        subjectField.val(subject);
                    }

                    var recipient = $('#id_send_to_normal').select2('data')[0];

                    if (typeof recipient !== 'undefined' && typeof recipient.object_id !== 'undefined') {
                        // Check if a contact has been entered
                        recipientId = recipient.object_id;
                    }
                    else if (self.config.sender !== '' && self.config.sender != null) {
                        // If it's a reply there might be contact set
                        recipientId = self.config.sender;
                        self.config.sender = null;
                    }

                    // Always get a template
                    var url = self.config.getTemplateUrl + selectedTemplate + '/';

                    if (recipientId != null) {
                        // If a recipient has been set we can set extra url parameters
                        url += '?contact_id=' + recipientId + '&emailaccount_id=' + emailAccountId;
                    }
                    else {
                        url += '?emailaccount_id=' + emailAccountId;
                    }

                    $.getJSON(url, function (data) {
                        self.setNewEditorValue(data, templateChanged);
                    });
                }
            }
        },

        handleInboxComposeSubmit: function (inboxCompose, event) {
            event.preventDefault();

            // Make sure replies on this email don't break the application
            editor.setValue(editor.getValue().replace(' id="compose-email-template"', ''));
            editor.setValue(editor.getValue().replace(' id="body-html-content"', ''));

            var buttonName = $(inboxCompose).attr('name'),
                $form = $($(inboxCompose).closest('form'));

            if (buttonName == 'submit-send') {
                // Validation of fields.
                if (!$('#id_send_to_normal').val() && !$('#id_send_to_cc').val() && !$('#id_send_to_bcc').val()) {
                    $('#modal_no_email_address').modal();
                    event.preventDefault();
                    return;
                }
            } else if (buttonName == 'submit-save') {
                var draftPk = $('#id_draft_pk').val();
                // If we are saving a (existing) draft, change url
                if(draftPk) {
                    $form.attr('action', '/messaging/email/draft/' + draftPk + '/');
                } else {
                    $form.attr('action', '/messaging/email/draft/');
                }
            } else if (buttonName == 'submit-discard') {
                // Discarding email, remove all attachments to prevent unneeded uploading.
                $('[id|=id_attachments]:file').remove();
            }

            // Make sure both buttons of the same name are set to the loading state
            $('button[name="' + buttonName + '"]').button('loading');

            // No validation needed, remove attachments to prevent unneeded uploading.
            $('[id|=id_attachments]:file').filter(function () {
                return $(inboxCompose).data('formset-disabled') == true;
            }).remove();

            Metronic.blockUI($('.inbox-content'), false, '');

            $form.submit();
        },

        handleTagsAjaxChange: function (tagsAjax) {
            // Select2 doesn't remove certain values (values with quotes), so make sure that the value of the field is correct
            var values = [];
            var data = $(tagsAjax).select2('data');

            for(var i=0; i < data.length; i++) {
                var recipient_data = data[i];
                values.push(recipient_data.id);
            }

            $(tagsAjax).val(values.join());
        },

        getEditor: function() {
            return editor;
        },

        loadDefaultEmailTemplate: function() {
            var self = this;
            var emailAccountId = $(self.config.emailAccountInput).val();
            var url = self.config.defaultEmailTemplateUrl + emailAccountId + '/';

            $.getJSON(url, function(data) {
                $(self.config.templateField).select2('val', data['template_id']).change();
            });
        },

        setNewEditorValue: function (data, templateChanged) {
            var self = this;
            var htmlPart = data['template'];
            // getValue returns a string, so convert to elements
            var editorValue = $(editor.getValue());
            var currentTemplate = editorValue.closest('#compose-email-template');
            var newEditorValue = '';

            // Check if an email template has already been loaded
            if (currentTemplate.length) {
                if (currentTemplate.html().length) {
                    var changeTemplate = false;

                    if (templateChanged) {
                        // If a different template was selected we want to warn the user
                        changeTemplate = confirm(self.config.overwriteTemplateConfirm);
                    }
                    else {
                        // Template wasn't changed, so a new recipient was entered
                        changeTemplate = true;
                    }

                    if (changeTemplate) {
                        // Change the html of the existing email template
                        currentTemplate.html(htmlPart);
                        // Since editorValue is actually an array of elements we can't easily convert it back to text
                        var container = $('<div>');
                        // Add the (edited) html to the newly created container
                        container.append(editorValue);
                        // Get the text version of the new html
                        newEditorValue = container[0].innerHTML;
                    }
                }
            }
            else {
                // No email template loaded so create our email template container
                var emailTemplate = '<div id="compose-email-template">' + htmlPart + '</div>';
                // Append the existing text
                newEditorValue = emailTemplate + '<br>' + editor.getValue();
            }

            if (newEditorValue.length) {
                editor.setValue(newEditorValue);
                self.resizeEditor();
                self.processAttachments(data['attachments']);
            }
        },

        processAttachments: function (attachments) {
            var cf = this.config;
            // Clear any existing template attachments
            $(cf.templateAttachmentsDiv).empty();

            var attachmentIds = [];

            for (var i = 0; i < attachments.length; i++) {
                var attachment = attachments[i];

                attachmentIds.push(attachment.id);

                var attachmentRow = $(cf.emptyTemplateAttachmentRow).clone();
                attachmentRow.find(cf.templateAttachmentName).html(attachment.name);
                attachmentRow.find(cf.templateAttachmentId).val(attachment.id);
                attachmentRow.removeAttr('id');
                attachmentRow.removeClass('hidden');

                $(cf.templateAttachmentsDiv).append(attachmentRow);
            }

            $(cf.templateAttachmentIds).val(attachmentIds);
        },

        handleTemplateAttachmentsChange: function (attachmentRow) {
            var self = this,
                cf = self.config;

            var rowAttachmentName = attachmentRow.find(cf.templateAttachmentName);

            if (rowAttachmentName.hasClass('mark-deleted')) {
                rowAttachmentName.removeClass('mark-deleted');
            }
            else {
                rowAttachmentName.addClass('mark-deleted');
            }

            attachmentRow.find('[data-formset-delete-button]').toggleClass('hidden');
            attachmentRow.find('[data-formset-undo-delete]').toggleClass('hidden');

            var newAttachmentIds = [];

            var attachments = $(cf.templateAttachmentRow);
            attachments.each(function () {
                if (!$(this).find(cf.templateAttachmentName).hasClass('mark-deleted')) {
                    var attachmentId = $(this).find(cf.templateAttachmentId).val();
                    if (attachmentId !== "") {
                        // Make sure the value of the empty attachment row doesn't get added
                        newAttachmentIds.push(attachmentId);
                    }
                }
            });

            $(cf.templateAttachmentIds).val(newAttachmentIds);
        }
    }
})(jQuery, window, document);
