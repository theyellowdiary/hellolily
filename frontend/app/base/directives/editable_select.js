angular.module('app.directives').directive('editableSelect', editableSelect);

function editableSelect() {
    return {
        restrict: 'E',
        scope: {
            viewModel: '=',
            field: '@',
            type: '@',
            choiceField: '@',
            search: '@?',
            multiple: '@?',
            selectType: '@?',
            object: '=?',
            selectOptions: '=?', // contains any custom settings for the select
        },
        templateUrl: (elem, attrs) => {
            if (attrs.selectType) {
                return 'base/directives/editable_' + attrs.selectType + '.html';
            }

            return 'base/directives/editable_select.html';
        },
        controller: EditableSelectController,
        controllerAs: 'es',
        transclude: true,
        bindToController: true,
        link: (scope, element, attr) => {
            // Bind click event to the current directive.
            element.on('click', '.editable-click', () => {
                if (scope.es.search) {
                    scope.es[scope.es.formName].$show();

                    scope.$apply();
                }
            });
        },
    };
}

EditableSelectController.$inject = ['$injector', '$scope', 'HLResource', 'HLSearch', 'HLUtils'];
function EditableSelectController($injector, $scope, HLResource, HLSearch, HLUtils) {
    const es = this;
    es.showDateIncrement = false;

    es.getChoices = getChoices;
    es.refreshChoices = refreshChoices;
    es.updateViewModel = updateViewModel;

    activate();

    // Broadcast function that executes the activate() function when somebody
    // dynamically changes the inline select edit by using the 'assign to me'
    // link, instead of selecting a person with the selectbox.
    $scope.$on('activateEditableSelect', () => {
        activate();
    });

    /////

    function activate() {
        if (!es.selectOptions) {
            // If it's undefined just set it to an empty object.
            // Ensures we don't need extra checks in the code.
            es.selectOptions = {};
        }

        if (!es.object) {
            es.object = es.viewModel[es.type.toLowerCase()];
        }

        // Certain values in the given view model are objects,
        // so the default value in the select won't always work.
        // If we're not dealing with an inline editable search select check
        // if it's an object and add .id.
        if (!es.search && typeof es.object[es.field] === 'object') {
            if (es.object[es.field]) {
                es.selectModel = es.object[es.field].id;
            }
        } else {
            es.selectModel = es.object[es.field];
        }

        if (es.selectOptions.hasOwnProperty('display')) {
            es.optionDisplay = es.selectOptions.display;
        } else {
            es.optionDisplay = 'name';
        }

        if (es.search) {
            if (es.selectOptions.hasOwnProperty('placeholder')) {
                es.placeholder = es.selectOptions.placeholder;
            }
        }

        es.showDateIncrement = (es.type === 'Case' || es.type === 'Deal');

        // Setup the form name so we can block the element while saving data.
        es.formName = es.field.split('_').join('') + 'Form';
    }

    function getChoices() {
        let type;

        if (es.selectOptions.hasOwnProperty('type')) {
            type = es.selectOptions.type;
        } else {
            type = es.type;
        }

        let field;

        if (es.selectOptions.hasOwnProperty('field')) {
            field = es.selectOptions.field;
        } else {
            field = es.field;
        }

        const resourceCall = HLResource.getChoicesForField(type, field);

        let returnValue = false;

        if (!resourceCall.hasOwnProperty('$promise')) {
            es.choices = resourceCall;
        } else {
            // Add a return here so the select gets disabled while
            // loading the options.
            returnValue = resourceCall.$promise.then(data => {
                if (data.hasOwnProperty('results')) {
                    es.choices = data.results;
                } else {
                    es.choices = data;
                }
            });
        }

        return returnValue;
    }

    function refreshChoices(query) {
        let sortColumn;
        let nameColumn;

        let type;

        if (es.selectOptions.hasOwnProperty('type')) {
            type = es.selectOptions.type;
        } else {
            type = es.type;
        }

        if (es.selectOptions.hasOwnProperty('sortColumn')) {
            sortColumn = es.selectOptions.sortColumn;
        }

        if (es.selectOptions.hasOwnProperty('nameColumn')) {
            nameColumn = es.selectOptions.nameColumn;
        }

        const extraFilterQuery = (type === 'User') ? 'is_active:true' : '';

        const searchPromise = HLSearch.refreshList(query, type, extraFilterQuery, sortColumn, nameColumn);

        if (searchPromise) {
            searchPromise.$promise.then(data => {
                es.choices = data.objects;
            });
        }
    }

    function updateViewModel($data) {
        let selected;

        const args = {
            id: es.object.id,
        };

        const form = `[name="es.${es.formName}"]`;

        if (!es.multiple) {
            // $data only contains the ID, so get the name from the choices in the scope.
            for (let i = 0; i < es.choices.length; i++) {
                if (es.choices[i].id === $data) {
                    selected = es.choices[i];
                }
            }
        } else {
            HLUtils.blockUI(form, true);
        }

        if (!es.multiple) {
            if (es.choiceField) {
                es.object[es.field] = $data;
                // Choice fields end with '_display', so set the proper
                // variable so front end changes are reflected properly.
                es.object[es.field + '_display'] = selected.name;
            } else {
                es.object[es.field] = selected;
            }
        }

        if (typeof $data === 'undefined') {
            // We're probably clearing a select field, which produces undefined.
            args[es.field] = null;
        } else {
            args[es.field] = $data;
        }

        let updatePromise;

        if (es.viewModel.hasOwnProperty('updateModel')) {
            updatePromise = es.viewModel.updateModel(args);
        } else {
            // Dealing with a generic view model (list widget, activity stream item) so just call the updateModel directly.
            updatePromise = $injector.get(es.type).updateModel(args, es.field, es.object);
        }

        return updatePromise.then(() => {
            HLUtils.unblockUI(form);

            if (es.hasOwnProperty(es.formName)) {
                es[es.formName].$hide();
            }

            if (es.search || es.selectType) {
                if (es.multiple) {
                    es.object[es.field] = $data;
                }

                // Inline editable select2 field doesn't properly update
                // es.selectModel, so update it manually.
                es.selectModel = es.object[es.field];
            }
        }).catch(() => {
            HLUtils.unblockUI(form);
        });
    }
}
